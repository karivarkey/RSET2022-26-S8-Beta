# ------------------------------------------------------------
#  task_extractor.py


# ------------------------------------------------------------

from __future__ import annotations
import re
from datetime import datetime, timedelta
import spacy
from dateutil import parser as dateparser
from typing import List, Dict, Optional
from zoneinfo import ZoneInfo
# ------------------------------------------------------------
# Load spaCy model (use sm for speed in backend)
# ------------------------------------------------------------
try:
    nlp = spacy.load("en_core_web_sm")
except:
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

# ------------------------------------------------------------
# Priority ordering
# ------------------------------------------------------------
PRIORITY_ORDER = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}

# ------------------------------------------------------------
# Action verbs used to detect tasks
# ------------------------------------------------------------
ACTION_VERBS = {
    "submit", "send", "review", "share", "prepare", "complete", "finalize",
    "update", "fix", "resolve", "arrange", "schedule", "meet", "follow",
    "remind", "check", "verify", "approve", "call", "email", "reply",
    "respond", "organize", "plan", "confirm", "draft", "collect"
}


def extract_due_date(text: str) -> Optional[str]:
   
    
    
    try:
        dt = dateparser.parse(text, fuzzy=True)

        if not dt:
            return None

        # If no timezone info → assume Asia/Kolkata
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("Asia/Kolkata"))

        # Convert to UTC for storage
        dt_utc = dt.astimezone(ZoneInfo("UTC"))

        return dt_utc.isoformat()

    except Exception:
        return None

# ------------------------------------------------------------
# Determine priority from keywords
# ------------------------------------------------------------
def estimate_priority(text: str) -> str:
    text_l = text.lower()

    if any(w in text_l for w in ["urgent", "immediately", "asap", "critical"]):
        return "Critical"
    if any(w in text_l for w in ["important", "high priority", "priority"]):
        return "High"
    if any(w in text_l for w in ["whenever", "no rush"]):
        return "Low"

    return "Medium"

# ------------------------------------------------------------
# Detect whether a sentence contains a task
# ------------------------------------------------------------
def is_task_sentence(sentence: str) -> bool:
    words = sentence.lower().split()
    return any(v in words for v in ACTION_VERBS)

# ------------------------------------------------------------
# Extract Named Entities (spaCy)
# ------------------------------------------------------------
def extract_entities(sentence: str) -> Dict:
    doc = nlp(sentence)
    people = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
    dates = [ent.text for ent in doc.ents if ent.label_ in ["DATE", "TIME"]]
    return {"people": people, "dates": dates}

# ------------------------------------------------------------
# Main: Convert summary → structured task list
# ------------------------------------------------------------
def extract_tasks(summary: str) -> List[Dict]:
    tasks = []
    sentences = [s.strip() for s in re.split(r"[.?!]\s*", summary) if s.strip()]

    for s in sentences:
        if not is_task_sentence(s):
            continue

        ents = extract_entities(s)
        due = extract_due_date(s)
        priority = estimate_priority(s)

        task = {
            "description": s,
            "priority": priority,
            "due_date": due,
            "people": ents["people"],
            "source": s
        }

        tasks.append(task)

    return tasks

# ------------------------------------------------------------
# Filter tasks to keep only those assigned to a specific user
# ------------------------------------------------------------
def filter_tasks_for_user(tasks: List[Dict], user_name: str) -> List[Dict]:
    filtered = []
    uname = user_name.lower()

    for t in tasks:
        # if no people in task → assume relevant
        if not t["people"]:
            filtered.append(t)
            continue

        # check if user is mentioned
        joined = " ".join(t["people"]).lower()
        if uname in joined:
            filtered.append(t)

    return filtered

# ------------------------------------------------------------
# Sort tasks by priority + due date
# ------------------------------------------------------------
def sort_tasks(tasks: List[Dict]) -> List[Dict]:
    def sort_key(t):
        pr = PRIORITY_ORDER.get(t["priority"], 1)
        due = t["due_date"] or ""
        return (-pr, due)

    return sorted(tasks, key=sort_key)

# ------------------------------------------------------------
# End of module
# ------------------------------------------------------------