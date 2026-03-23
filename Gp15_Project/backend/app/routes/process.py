from pydoc import text
from fastapi import APIRouter
from app.schemas.email import EmailInput
from app.schemas.classification import ClassificationOutput
# from app.routes.classify import classify_email
from app.routes.summarize import summarize_email
from app.routes.tasks import extract_tasks
from app.core.db import insert_email, insert_summary, insert_tasks
from app.ml.classifier import classify_proba
from app.routes.tasks import extract_tasks as extract_tasks_backend



router = APIRouter()

@router.post("/")
def process_email(email: EmailInput):
    # classification = classify_email(email)
    text = email.subject + " " + email.body
    label, confidence = classify_proba(text)

    classification = {
    "is_corporate": (label.lower() == "corporate"),
    "confidence": confidence,
    "category": label.lower()
}

    if not classification["is_corporate"]:
        return {
            "is_corporate": False,
            "message": "Non-corporate email ignored"
        }



   # 1. Insert email
    email_row = insert_email({
        "subject": email.subject,
        "sender": email.sender,
        "body": email.body,
        "is_corporate": classification["is_corporate"],
        "confidence": classification["confidence"],
        "category": classification["category"],
        "user_id": None  # will be added later
    })
    
    
    
    
    summary = summarize_email(email)
    insert_summary({
        "email_id": email_row["id"],
        "summary": summary["summary"]
    })
    
     # 3. Generate & insert tasks
    # tasks_output = extract_tasks(email)
    tasks_output = extract_tasks_backend(email)
    task_rows = []

    for task in tasks_output["tasks"]:
        task_rows.append({
            "email_id": email_row["id"],
            "title": task["title"],
            "due_date": task.get("due_date"),
            "priority": task["priority"]
        })

    if task_rows:
        insert_tasks(task_rows)

    return {
        "is_corporate": True,
        "email_id": email_row["id"],
        "summary": summary,
        "tasks": tasks_output
    }