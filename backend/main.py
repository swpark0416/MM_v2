import os
import random
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from notion_client import Client
import requests

app = FastAPI(title="Habit Tower Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 환경 변수 로드
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
DATABASE_ID = os.getenv("DATABASE_ID", "")
QUOTE_DATABASE_ID = os.getenv("QUOTE_DATABASE_ID", "")
TEXT_DATABASE_ID = os.getenv("TEXT_DATABASE_ID", "")  # 신규 텍스트 DB ID

notion = Client(auth=NOTION_TOKEN)
CATEGORIES = ["공부", "취미", "외면", "내면"]


# --- Pydantic 모델 정의 ---
class HabitCreate(BaseModel):
    title: str
    category: str
    status: str = "보유 습관"
    level: str = "중"


class HabitUpdate(BaseModel):
    level: Optional[str] = None
    status: Optional[str] = None


class MissionRequest(BaseModel):
    content: str


class TextRecord(BaseModel):
    category: str  # "명상", "사명서", "운동", "감사"
    content: str


# --- 습관(Habit Tower) API ---
@app.get("/api/habits")
def get_habits():
    """노션 습관 DB에서 습관 목록을 조회하여 영역별로 분류합니다."""
    owned_habits = {cat: [] for cat in CATEGORIES}
    wish_habits = {cat: [] for cat in CATEGORIES}
    all_habits_flat = []

    try:
        headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
        res = requests.post(url, headers=headers)

        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail="Notion API 연동 실패")

        query_res = res.json()
        for page in query_res.get("results", []):
            page_id = page["id"]
            props = page["properties"]

            st_obj = props.get("습관 상태", {}).get("select")
            st_name = st_obj["name"] if st_obj else "보유 습관"

            if st_name == "사명서":
                continue

            title_list = props.get("Name", {}).get("title", [])
            h_title = title_list[0]["text"]["content"] if title_list else None
            cat_obj = props.get("영역", {}).get("select")
            cat_name = cat_obj["name"] if cat_obj else None

            level_obj = props.get("수준", {}).get("select")
            level_name = level_obj["name"] if level_obj else "중"

            if h_title and cat_name in CATEGORIES:
                item = {
                    "id": page_id,
                    "title": h_title,
                    "category": cat_name,
                    "status": st_name,
                    "level": level_name,
                }
                all_habits_flat.append(item)

                if st_name == "보유 습관":
                    owned_habits[cat_name].append(item)
                else:
                    wish_habits[cat_name].append(item)

        return {"owned": owned_habits, "wish": wish_habits, "all": all_habits_flat}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/habits")
def create_habit(habit: HabitCreate):
    """새로운 습관을 노션 DB에 추가합니다."""
    try:
        response = notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties={
                "Name": {"title": [{"text": {"content": habit.title}}]},
                "영역": {"select": {"name": habit.category}},
                "습관 상태": {"select": {"name": habit.status}},
                "수준": {"select": {"name": habit.level}},
            },
        )
        return {"status": "success", "id": response["id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/habits/{page_id}")
def update_habit(page_id: str, habit: HabitUpdate):
    """습관의 수준 또는 상태를 업데이트합니다."""
    try:
        props = {}
        if habit.level:
            props["수준"] = {"select": {"name": habit.level}}
        if habit.status:
            props["습관 상태"] = {"select": {"name": habit.status}}

        if props:
            notion.pages.update(page_id=page_id, properties=props)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/habits/{page_id}")
def delete_habit(page_id: str):
    """지정한 ID의 습관을 아카이브(삭제) 처리합니다."""
    try:
        notion.pages.update(page_id=page_id, archived=True)
        return {"status": "success", "message": "삭제 완료"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- 신규 텍스트 DB API (명상, 사명서, 운동, 감사일기 통합) ---
@app.get("/api/texts")
def get_texts():
    """신규 텍스트 DB(TEXT_DATABASE_ID)에서 카테고리별 최근 최신 텍스트를 조회합니다."""
    records = {"명상": "", "사명서": "", "운동": "", "감사": ""}
    if not TEXT_DATABASE_ID:
        return records

    try:
        headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        url = f"https://api.notion.com/v1/databases/{TEXT_DATABASE_ID}/query"
        res = requests.post(url, headers=headers)

        if res.status_code == 200:
            results = res.json().get("results", [])
            for page in results:
                props = page.get("properties", {})
                cat_obj = props.get("카테고리", {}).get("select")
                cat_name = cat_obj["name"] if cat_obj else None

                content_list = props.get("내용", {}).get("rich_text", [])
                content = content_list[0]["text"]["content"] if content_list else ""

                if cat_name in records and not records[cat_name]:
                    records[cat_name] = content

        return records
    except Exception as e:
        print("텍스트 데이터 조회 에러:", e)
        return records


@app.post("/api/texts")
def save_text(record: TextRecord):
    """신규 텍스트 DB에 카테고리별(명상, 사명서, 운동, 감사) 레코드를 생성하거나 업서트(Upsert)합니다."""
    if not TEXT_DATABASE_ID:
        raise HTTPException(status_code=400, detail="TEXT_DATABASE_ID 환경변수가 설정되지 않았습니다.")

    try:
        headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        
        # 카테고리가 일치하는 기존 페이지 검색
        query_url = f"https://api.notion.com/v1/databases/{TEXT_DATABASE_ID}/query"
        body = {
            "filter": {
                "property": "카테고리",
                "select": {"equals": record.category}
            }
        }
        res = requests.post(query_url, headers=headers, json=body)
        
        target_page_id = None
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results:
                target_page_id = results[0]["id"]

        if target_page_id:
            # 기존 페이지 내용 업데이트
            notion.pages.update(
                page_id=target_page_id,
                properties={
                    "내용": {
                        "rich_text": [{"text": {"content": record.content}}]
                    }
                }
            )
        else:
            # 신규 페이지 생성
            notion.pages.create(
                parent={"database_id": TEXT_DATABASE_ID},
                properties={
                    "Name": {"title": [{"text": {"content": f"{record.category} 기록"}}]},
                    "카테고리": {"select": {"name": record.category}},
                    "내용": {
                        "rich_text": [{"text": {"content": record.content}}]
                    },
                },
            )
        return {"status": "success", "message": f"{record.category} 저장 완료"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- 기존 사명서 호환용 레거시 API ---
@app.get("/api/mission")
def get_mission():
    return get_texts()


@app.post("/api/mission")
def save_mission(data: MissionRequest):
    return save_text(TextRecord(category="사명서", content=data.content))


# --- 독서/명구절 API ---
@app.get("/api/quotes/random")
def get_random_quotes():
    """노션 독서 DB에서 저장된 명구절 중 무작위로 최대 5개를 추출하여 반환합니다."""
    if not QUOTE_DATABASE_ID:
        return {"quotes": [{"quote": "설정된 독서 DB가 없습니다.", "source": "시스템"}]}

    try:
        headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        url = f"https://api.notion.com/v1/databases/{QUOTE_DATABASE_ID}/query"
        res = requests.post(url, headers=headers)

        if res.status_code == 200:
            results = res.json().get("results", [])
            quotes_list = []

            for page in results:
                props = page.get("properties", {})

                quote_text = ""
                for prop_val in props.values():
                    if prop_val.get("type") == "title" and prop_val.get("title"):
                        quote_text = prop_val["title"][0].get("plain_text", "")
                        break

                source_obj = props.get("출처", {})
                source_text = ""
                stype = source_obj.get("type")

                if stype == "select" and source_obj.get("select"):
                    source_text = source_obj["select"].get("name", "")
                elif stype == "rich_text" and source_obj.get("rich_text"):
                    source_text = source_obj["rich_text"][0].get("plain_text", "")

                if quote_text:
                    quotes_list.append({"quote": quote_text, "source": source_text or "출처 미상"})

            if quotes_list:
                sample_count = min(5, len(quotes_list))
                return {"quotes": random.sample(quotes_list, sample_count)}

        return {"quotes": [{"quote": "등록된 명구절이 없습니다.", "source": "Miracle Morning"}]}
    except Exception as e:
        print("명언 조회 에러:", e)
        return {"quotes": [{"quote": "명언을 불러오는 중 오류가 발생했습니다.", "source": "에러"}]}
