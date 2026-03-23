





from fastapi import APIRouter
from app.schemas.email import EmailInput
from pydantic import BaseModel
from typing import List, Optional

from app.ml.task_extractor.task_extractor import extract_tasks as ml_extract
from app.core.db import supabase
from zoneinfo import ZoneInfo
from dateutil import parser



router = APIRouter()

class Task(BaseModel):
    title: str
    due_date: Optional[str] = None
    priority: str
    context: Optional[str] = None
    source_sentence: Optional[str] = None
    

    
class TaskListOutput(BaseModel):
    tasks: List[Task]

class SaveTasksInput(BaseModel):
    email_id: str
    tasks: List[Task]
    
def fix_timezone(dt_str: str | None):
    if not dt_str:
        return None
   
    
    try:
        dt = parser.isoparse(dt_str)

        # If the timestamp has NO timezone → assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))

        # Convert UTC → IST
        return dt.astimezone(ZoneInfo("UTC")).isoformat()

    except Exception:
        return dt_str
    

# ------------------------------------------------------------
# CLEAN TITLE (Option B) - Remove polite words & fix casing
# ------------------------------------------------------------
def clean_title(description: str, subject: str = "") -> str:
    desc = description.strip()

    # Remove subject if it appears inside
    if subject and subject.lower() in desc.lower():
        desc = desc.replace(subject, "", 1).strip()

    # Remove greetings
    greetings = ["hi ", "hi eby", "hello ", "dear ", "hey "]
    d = desc.lower()
    for g in greetings:
        if d.startswith(g):
            desc = desc[len(g):].strip()
            break

    # Polite prefixes to remove
    polite_prefixes = [
        "please ", "kindly ", "can you ", "could you ",
        "i request you to ", "i request you ", "pls ",
        "please do ", "please make sure to "
    ]

    d = desc.lower()
    for p in polite_prefixes:
        if d.startswith(p):
            desc = desc[len(p):]
            break

    # Capitalize first character
    if desc:
        desc = desc[0].upper() + desc[1:]

    return desc.strip()


# ------------------------------------------------------------
# TAIL SENTENCES EXTRACTION (Option B)
# ------------------------------------------------------------
def extract_tail_sentences(body: str, count: int = 2) -> str:
    parts = [s.strip() for s in body.split('.') if s.strip()]
    if not parts:
        return ""
    return ". ".join(parts[-count:])


# ------------------------------------------------------------
# GARBAGE TASK FILTER  (NEW)
# ------------------------------------------------------------
def is_garbage(title: str) -> bool:
    """
    Filters out marketing/garbage tasks generated from promotional
    or tracking-heavy emails (LinkedIn, newsletters, ads, etc.)
    """

    t = title.lower()

    # URL / tracking detection
    if "http://" in t or "https://" in t:
        return True
    if "utm_" in t or "trk=" in t or "tracking" in t:
        return True

    # Common marketing / promotional noise
    garbage_phrases = [
        "unsubscribe", "premium", "help:", "learn why",
        "profile views", "view profile", "notification",
        "upgrade", "unlock", "get more", "see more",
        "your profile is looking great"
    ]
    for phrase in garbage_phrases:
        if phrase in t:
            return True

    # Long sentences are rarely real tasks
    if len(t) > 120:
        return True

    # Must contain at least one actionable verb
    verbs = [
        "submit", "prepare", "schedule", "review", "complete",
        "finish", "update", "send", "call", "meet", "finalize",
        "draft", "attach", "upload"
    ]
    if not any(v in t for v in verbs):
        return True

    return False


# ------------------------------------------------------------
# MAIN TASK EXTRACTOR ENDPOINT
# ------------------------------------------------------------
@router.post("/extract", response_model=TaskListOutput)
def extract_tasks(email: EmailInput):
    """
    ML-based task extraction:
    - summary (if provided)
    - OR body fallback
    - last 2 sentences (Option B)
    - filtered for garbage tasks
    """

    # 1) Summary extraction
    summary_text = ""
    if hasattr(email, "summary") and email.summary:
        if isinstance(email.summary, dict):
            summary_text = email.summary.get("summary", "")
        elif isinstance(email.summary, tuple):
            summary_text = email.summary[0]
        else:
            summary_text = str(email.summary)
    else:
        summary_text = email.body

    # 2) Extract last 2 sentences from body (Option B)
    tail_text = extract_tail_sentences(email.body, count=2)

    # 3) Combine summary + tail
    combined_text = f"{summary_text}. {tail_text}"

    # 4) Run ML extraction
    raw_tasks = ml_extract(combined_text)

    # 5) Convert, clean, dedupe, filter garbage
    unique = {}

    for t in raw_tasks:
        raw_desc = t.get("description", "")
        title = clean_title(raw_desc, subject=email.subject)
        
        print("RAW ML due_date:", t.get("due_date"))
        if not title:
            continue

        #  Skip marketing/garbage tasks
        if is_garbage(title):
            continue

        #  Deduplicate based on title
        if title not in unique:
            unique[title] = {
                "title": title,
                "due_date": fix_timezone(t.get("due_date")),
                "priority": t.get("priority", "medium").lower(),
                "context": f"From email: {email.subject}",
                "source_sentence": raw_desc
            }
        print("RAW TASKS FROM ML:", raw_tasks)

    return {"tasks": list(unique.values())}




@router.post("/save")
def save_tasks(payload: SaveTasksInput):
    saved = []

    for task in payload.tasks:
        res = supabase.table("tasks").insert({
            "email_id": payload.email_id,
            "title": task.title,
            "due_date": task.due_date,
            "priority": task.priority,
            "context": task.context,
            "source_sentence": task.source_sentence,
            "completed": False
        }).execute()

        saved.append(res.data)
        
        print("Saving tasks:", payload.tasks)

    return {"status": "saved", "tasks": saved}



# ------------------------------------------------------------
# GET TASKS (REAL SUPABASE QUERY)
# ------------------------------------------------------------
# @router.get("/tasks")
# def get_tasks(completed: bool = False):
#     res = (
#         supabase.table("tasks")
#         .select("*")
#         .eq("completed", completed)
#         .order("created_at", desc=False)
#         .execute()
#     )

#     return res.data

# ------------------------------------------------------------
# PATCH UPDATE COMPLETED
# ------------------------------------------------------------



@router.patch("/{task_id}")
def update_task(task_id: str, payload: dict):
    from app.core.db import supabase

    allowed_fields = ["title", "due_date", "priority", "completed"]
    updates = {k: v for k, v in payload.items() if k in allowed_fields}

    if not updates:
        return {"error": "No valid fields to update"}

    # 1️ Update row
    update_res = (
        supabase
        .table("tasks")
        .update(updates)
        .eq("id", task_id)
        .execute()
    )

    print("Update response:", update_res)

    # 2️ Fetch updated row
    fetch_res = (
        supabase
        .table("tasks")
        .select("*")
        .eq("id", task_id)
        .single()
        .execute()
    )

    print("Fetch response:", fetch_res)

    if fetch_res.data:
        return fetch_res.data

    return {"error": "Task not found"}





@router.delete("/{task_id}")
def delete_task(task_id: str):
    from app.core.db import supabase

    res = (
        supabase.table("tasks")
        .delete()
        .eq("id", task_id)
        .execute()
    )

    return {"status": "deleted", "task_id": task_id}




@router.get("")
def get_tasks(completed: str | None= None):
    from app.core.db import supabase
     
    print("Completed param received:", completed)

     
    query = supabase.table("tasks").select("*")
    
    
    # if completed is not None:
    #     query = query.eq("completed", completed)
    
    if completed == "true":
        query = query.eq("completed", True)
    elif completed == "false":
        query = query.eq("completed", False)
    
    
    
    res = query.order("created_at", desc=True).execute()

    print("Returned rows:", len(res.data))
    return res.data













# @router.get("/tasks")
# def get_tasks(completed: bool = False):
#     """
#     Dummy corporate-grade tasks.
#     This shape is FINAL and ML will later replace values.
#     """

#     tasks = [
#         {
#             "title": "Submit Q4 budget report",
#             "due_date": "2026-01-05T17:00:00",
#             "priority": "high",
#             "context": "Requested by Finance team via corporate email",
#             "source_sentence": "Please submit the Q4 budget report by Jan 5 EOD",
#             "completed": False
#         },
#         {
#             "title": "Client review meeting with ABC Corp",
#             "due_date": "2026-01-10T15:00:00",
#             "priority": "high",
#             "context": "Meeting scheduled with external client",
#             "source_sentence": "Let's have a review call on Jan 10 at 3 PM",
#             "completed": False
#         }
#     ]

#     return tasks




# # @router.post("/extract", response_model=TaskListOutput)
# # def extract_tasks(email: EmailInput):
# #     return {
# #         "tasks": [
# #             {
# #                 "title": "Submit Q4 budget report",
# #                 "due_date": "2026-01-05T17:00:00",
# #                 "priority": "high"
# #             }
# #         ]
# #     }


