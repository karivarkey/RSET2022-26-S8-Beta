from fastapi import APIRouter
from app.core.db import get_summaries, get_tasks

router = APIRouter()

@router.get("/summaries")
def fetch_summaries():
    return get_summaries()


@router.get("/tasks")
def fetch_tasks(completed: bool = False):
    return get_tasks(completed)


# @router.get("/summaries")
# def get_summaries():
#     res = supabase.table("summaries").select("summary, confidence").execute()
#     return res.data
