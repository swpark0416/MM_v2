import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from notion_client import Client
import requests
import random

app = FastAPI(title="Habit Tower Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

NOTION_TOKEN = os.getenv("NOTION_TOKEN", "YOUR_NOTION_TOKEN_HERE")
DATABASE_ID = os.getenv("DATABASE_ID", "YOUR_DATABASE_ID_HERE")

notion = Client(auth=NOTION_TOKEN)
CATEGORIES = ["공부", "취미", "외면", "내면"]


class HabitCreate(BaseModel):
    title: str
    category: str
    status: str = "보유 습관"
    level: str = "중"  # 상, 중, 하


class HabitUpdate(BaseModel):
    level: Optional[str] = None
    status: Optional[str] = None


class MissionRequest(BaseModel):
    content: str


@app.get("/api/habits")
def get_habits():
    """노션에서 습관 목록을 가져와 영역별로 분류합니다."""
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
            raise HTTPException(
                status_code=res.status_code, detail="Notion API 연동 실패"
            )

        query_res = res.json()
        for page in query_res.get("results", []):
            page_id = page["id"]
            props = page["properties"]

            # 습관 상태 검사
            st_obj = props.get("습관 상태", {}).get("select")
            st_name = st_obj["name"] if st_obj else "보유 습관"

            # 💡 '사명서' 태그가 달린 데이터는 습관 탑 목록에서 제외
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
    """새로운 습관을 노션에 등록합니다."""
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
    """습관의 수준(상/중/하) 또는 상태(보유 습관/만들고 싶은 습관)를 변경합니다."""
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
    """지정한 ID의 습관을 노션에서 삭제(아카이브)합니다."""
    try:
        notion.pages.update(page_id=page_id, archived=True)
        return {"status": "success", "message": "삭제 완료"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mission")
def get_mission():
    """노션 DB에서 '사명서' 항목을 조회합니다."""
    try:
        headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
        body = {
            "filter": {
                "property": "습관 상태",
                "select": {"equals": "사명서"}
            }
        }
        res = requests.post(url, headers=headers, json=body)

        if res.status_code == 200:
            query_res = res.json()
            results = query_res.get("results", [])
            if results:
                title_props = results[0].get("properties", {}).get("Name", {}).get("title", [])
                if title_props:
                    return {"mission": title_props[0].get("plain_text", "")}

        return {"mission": ""}
    except Exception as e:
        print("사명서 조회 에러:", e)
        return {"mission": ""}


@app.post("/api/mission")
def save_mission(data: MissionRequest):
    """노션 DB에 사명서를 저장하거나 업데이트합니다."""
    try:
        headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
        body = {
            "filter": {
                "property": "습관 상태",
                "select": {"equals": "사명서"}
            }
        }
        res = requests.post(url, headers=headers, json=body)

        target_page_id = None
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results:
                target_page_id = results[0]["id"]

        if target_page_id:
            # 기존 사명서 페이지 업데이트
            notion.pages.update(
                page_id=target_page_id,
                properties={
                    "Name": {"title": [{"text": {"content": data.content}}]}
                },
            )
        else:
            # 신규 사명서 페이지 생성
            notion.pages.create(
                parent={"database_id": DATABASE_ID},
                properties={
                    "Name": {"title": [{"text": {"content": data.content}}]},
                    "영역": {"select": {"name": "내면"}},
                    "습관 상태": {"select": {"name": "사명서"}},
                    "수준": {"select": {"name": "중"}},
                },
            )
        return {"status": "success", "message": "사명서가 노션에 저장되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


QUOTE_DATABASE_ID = os.getenv("QUOTE_DATABASE_ID", "")


@app.get("/api/quotes/random")
def get_random_quotes():
    """노션 독서 DB에서 저장된 명구절 중 무작위로 최대 5개를 뽑아 반환합니다."""
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

                # 1. Name (명문장 본문) 파싱 - 첫번째 Title 속성 안전하게 추출
                quote_text = ""
                for prop_val in props.values():
                    if prop_val.get("type") == "title" and prop_val.get("title"):
                        quote_text = prop_val["title"][0].get("plain_text", "")
                        break

                # 2. 출처 파싱 (선택, 텍스트 등 유연하게 다 감지)
                source_obj = props.get("출처", {})
                source_text = ""
                stype = source_obj.get("type")
                
                if stype == "select" and source_obj.get("select"):
                    source_text = source_obj["select"].get("name", "")
                elif stype == "rich_text" and source_obj.get("rich_text"):
                    source_text = source_obj["rich_text"][0].get("plain_text", "")

                # 문장 본문이 확인되면 목록에 삽입
                if quote_text:
                    quotes_list.append(
                        {
                            "quote": quote_text,
                            "source": source_text or "출처 미상",
                        }
                    )

            if quotes_list:
                sample_count = min(5, len(quotes_list))
                selected_quotes = random.sample(quotes_list, sample_count)
                return {"quotes": selected_quotes}

        return {
            "quotes": [
                {
                    "quote": "아직 등록된 명구절이 없습니다. 노션 DB에 문장을 추가해 보세요!",
                    "source": "Miracle Morning",
                }
            ]
        }
    except Exception as e:
        print("명언 조회 에러:", e)
        return {
            "quotes": [
                {
                    "quote": "명언을 불러오는 중 오류가 발생했습니다.",
                    "source": "에러",
                }
            ]
        }