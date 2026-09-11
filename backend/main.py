import os
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

            title_list = props.get("Name", {}).get("title", [])
            h_title = title_list[0]["text"]["content"] if title_list else None
            cat_obj = props.get("영역", {}).get("select")
            cat_name = cat_obj["name"] if cat_obj else None
            st_obj = props.get("습관 상태", {}).get("select")
            st_name = st_obj["name"] if st_obj else "보유 습관"
            
            level_obj = props.get("수준", {}).get("select")
            level_name = level_obj["name"] if level_obj else "중"

            if h_title and cat_name in CATEGORIES:
                item = {
                    "id": page_id,
                    "title": h_title,
                    "category": cat_name,
                    "status": st_name,
                    "level": level_name
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


from pydantic import BaseModel

# 사명서 데이터 요청 모델
class MissionRequest(BaseModel):
    content: str

@app.get("/api/mission")
def get_mission():
    """노션 DB에서 사명서 블록을 조회합니다."""
    try:
        # 노션 DB 내 'Affirmation' 또는 '사명서' 항목 검색
        response = notion.databases.query(
            database_id=NOTION_DATABASE_ID,
            filter={"property": "영역", "select": {"equals": "내면"}}  # 내면 카테고리 활용
        )
        results = response.get("results", [])
        for page in results:
            title_props = page["properties"]["Name"]["title"]
            if title_props and "사명서" in title_props[0]["plain_text"]:
                # 노션 페이지 내 텍스트 가져오기 (또는 수준/상태 필드에 저장된 content 가져오기)
                return {"mission": page.get("properties", {}).get("사명서_내용", {}).get("rich_text", [{}])[0].get("plain_text", "")}
        
        return {"mission": ""}
    except Exception as e:
        print("사명서 조회 실패:", e)
        return {"mission": ""}

@app.post("/api/mission")
def save_mission(data: MissionRequest):
    """노션 DB에 작성된 사명서를 저장/수정합니다."""
    try:
        # 기존 사명서 페이지 검색 후 Update 또는 새 페이지 Create
        response = notion.databases.query(
            database_id=NOTION_DATABASE_ID,
            filter={"property": "영역", "select": {"equals": "내면"}}
        )
        results = response.get("results", [])
        target_page_id = None
        
        for page in results:
            title_props = page["properties"]["Name"]["title"]
            if title_props and "사명서" in title_props[0]["plain_text"]:
                target_page_id = page["id"]
                break

        if target_page_id:
            # 기존 페이지 수정
            notion.pages.update(
                page_id=target_page_id,
                properties={
                    "Name": {"title": [{"text": {"content": "📜 사명서"}}]}
                }
            )
        else:
            # 신규 사명서 페이지 생성
            notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties={
                    "Name": {"title": [{"text": {"content": "📜 사명서"}}]},
                    "영역": {"select": {"name": "내면"}},
                    "습관 상태": {"select": {"name": "보유 습관"}}
                }
            )
        return {"status": "success", "message": "사명서가 노션에 저장되었습니다."}
    except Exception as e:
        return {"status": "error", "message": str(e)}