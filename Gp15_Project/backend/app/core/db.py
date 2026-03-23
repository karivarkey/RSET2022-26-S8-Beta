from app.core.supabase import supabase

def insert_email(email_data: dict):
    response = supabase.table("emails").insert(email_data).execute()
    return response.data[0]

def insert_summary(summary_data: dict):
    response = supabase.table("summaries").insert(summary_data).execute()
    return response.data[0]

def insert_tasks(tasks: list):
    response = supabase.table("tasks").insert(tasks).execute()
    return response.data



def get_summaries():
        result = supabase.table("summaries") \
            .select("summary, confidence, emails(subject, sender,has_attachment)") \
            .order("created_at", desc=True) \
            .execute()

        formatted = []

        for row in result.data:
            formatted.append({
                "summary": row["summary"],
                "confidence": row["confidence"],
                "subject": row["emails"]["subject"] if row.get("emails") else "",
                "sender": row["emails"]["sender"] if row.get("emails") else "",
                "has_attachment": row["emails"]["has_attachment"] if row.get("emails") else False
        })

        return formatted


def get_tasks(completed: bool = False):
    response = (
        supabase
        .table("tasks")
        .select("id, title, due_date, priority,context,completed, email_id")
        .eq("completed", completed)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data
