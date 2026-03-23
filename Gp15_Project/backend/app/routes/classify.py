






from cProfile import label
from fastapi import APIRouter
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.routes.calendar import TOKEN_STORE, CLIENT_ID, CLIENT_SECRET
from app.ml.classifier import classify_proba
from app.ml.category_classifier import detect_category    # <-- NEW
from email import message_from_bytes
import base64
from app.ml.category_classifier import detect_category

router = APIRouter()


# def decode_email_body(msg):
#     if msg.get("parts"):
#         for part in msg["parts"]:
#             try:
#                 data = part["body"]["data"]
#                 decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
#                 return decoded
#             except:
#                 continue
#     try:
#         data = msg["body"]["data"]
#         decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
#         return decoded
#     except:
#         return ""
def decode_email_body(payload):
    body = ""

    if "parts" in payload:
        for part in payload["parts"]:
            # Look for text/plain part
            if part.get("mimeType") == "text/plain":
                data = part["body"].get("data")
                if data:
                    body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                    return body

            # Sometimes nested parts
            if "parts" in part:
                for subpart in part["parts"]:
                    if subpart.get("mimeType") == "text/plain":
                        data = subpart["body"].get("data")
                        if data:
                            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                            return body

    # fallback (single-part email)
    if payload.get("body", {}).get("data"):
        data = payload["body"]["data"]
        body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    return body



@router.get("/list")
def list_emails():
    if "access_token" not in TOKEN_STORE:
        return {"error": "User not authenticated"}

    creds = Credentials(
        token=TOKEN_STORE["access_token"],
        refresh_token=TOKEN_STORE["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )

    service = build("gmail", "v1", credentials=creds)

    result = service.users().messages().list(
        userId="me", maxResults=20
    ).execute()

    messages = result.get("messages", [])
    output = []

    for m in messages:
        msg = service.users().messages().get(
            userId="me", id=m["id"], format="full"
        ).execute()

        headers = msg["payload"]["headers"]
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "")

        body = decode_email_body(msg["payload"])

        # ---- ML classifier (corporate/non-corporate) ----
        label, confidence = classify_proba(subject + " " + body)
        is_corporate = (label == "corporate")

        print(" DEBUG: classify.py is running")
        # ---------------------------------------------
        # BUSINESS KEYWORD BOOST (Rule-based override)
        # ---------------------------------------------
        business_keywords = [
            "project", "status", "update", "action", "required",
            "deliverable", "review", "meeting", "schedule",
            "submit", "report", "documentation", "deadline"
        ]

        subject_lower = subject.lower()

        # If subject contains corporate/business words → force corporate
        if any(word in subject_lower for word in business_keywords):
            is_corporate = True
        
        # NEW → detect detailed category only if corporate
        # if label == "corporate":
        if is_corporate:
          detailed = detect_category(subject + " " + body)
        else:
            detailed = "none"
        # ---- NEW: category detection ----
        category = detect_category(subject, body)

        output.append({
            "id": m["id"],
            "subject": subject,
            "sender": sender,
            "body": body[:500],
            # "is_corporate": label.lower(),
            "is_corporate": is_corporate,
            "category": category,         # <---- NEW CATEGORY
            "confidence": confidence,
             "detailed_category": detailed,
        })

    return {"emails": output}












