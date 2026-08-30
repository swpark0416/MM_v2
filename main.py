import os
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


class HabitToggle(BaseModel):
    completed: bool


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
            
            # 완료 체크박스 상태 읽기 (기본값 False)
            is_completed = props.get("완료", {}).get("checkbox", False)

            if h_title and cat_name in CATEGORIES:
                item = {
                    "id": page_id,
                    "title": h_title,
                    "category": cat_name,
                    "status": st_name,
                    "completed": is_completed
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
                "완료": {"checkbox": False}
            },
        )
        return {"status": "success", "id": response["id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/habits/{page_id}/toggle")
def toggle_habit(page_id: str, toggle: HabitToggle):
    """습관 블록 완료/미완료 토글"""
    try:
        notion.pages.update(
            page_id=page_id,
            properties={
                "완료": {"checkbox": toggle.completed}
            }
        )
        return {"status": "success", "completed": toggle.completed}
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
