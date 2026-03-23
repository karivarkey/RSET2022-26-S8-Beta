from fastapi import APIRouter, Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import os
from fastapi.responses import RedirectResponse
from fastapi import HTTPException
from google.oauth2.credentials import Credentials
from fastapi import Body
from datetime import datetime, timedelta
from app.core.supabase import supabase
from zoneinfo import ZoneInfo
from dateutil import parser

router = APIRouter()

# TEMP storage (OK for now)
TOKEN_STORE = {}


CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/calendar/callback"

SCOPES = ["https://www.googleapis.com/auth/calendar.events",
          "https://www.googleapis.com/auth/gmail.readonly"]

@router.get("/auth")
def google_auth():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uris": [REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES
    )

    flow.redirect_uri = REDIRECT_URI
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true"
    )

    # return {"auth_url": auth_url}
    return RedirectResponse(auth_url)


@router.get("/callback")
def google_callback(request: Request):
    code = request.query_params.get("code")

    if not code:
        raise HTTPException(status_code=400, detail="Missing auth code")

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uris": [REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES
    )

    flow.redirect_uri = REDIRECT_URI

    # Exchange code for tokens
    flow.fetch_token(code=code)

    credentials: Credentials = flow.credentials
    
    
    user_id="5255d7c4-60ad-4120-941f-94ae6ebbbc3d"



    
    
    
    # user_id = request.state.user.id  # Supabase user
    supabase.table("google_accounts").upsert({
        "user_id": user_id,
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "expires_at": credentials.expiry.isoformat(),
        "email": credentials.id_token.get("email") if credentials.id_token else None
    }).execute()
     
     
    # Store tokens (TEMP – later we move to DB)
    TOKEN_STORE["access_token"] = credentials.token
    TOKEN_STORE["refresh_token"] = credentials.refresh_token
    TOKEN_STORE["expiry"] = credentials.expiry.isoformat()

    return {
        "message": "Google Calendar authorization successful",
        "access_token_present": credentials.token is not None,
        "refresh_token_present": credentials.refresh_token is not None
    }
    
    
@router.post("/push")
def push_task_to_calendar(
    title: str = Body(...),
    due_date: str = Body(...)
):
    if "access_token" not in TOKEN_STORE:
        return {"error": "User not authenticated with Google"}

    credentials = Credentials(
        token=TOKEN_STORE["access_token"],
        refresh_token=TOKEN_STORE["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )

    service = build("calendar", "v3", credentials=credentials)

    start_time = parser.isoparse(due_date)                               
    end_time = start_time + timedelta(hours=1)
    print("RAW due_date received:", due_date)

    event = {
        "summary": title,
        "start": {
            "dateTime": start_time.isoformat(),
            # "timeZone": "Asia/Kolkata"
        },
        "end": {
            "dateTime": end_time.isoformat(),
            # "timeZone": "Asia/Kolkata"
        }
    }
    
    
    print("Converted IST:", start_time)
    print("Final calendar start time:", start_time, start_time.tzinfo)



    created_event = service.events().insert(
        calendarId="primary",
        body=event
    ).execute()

    return {
        "message": "Event created successfully",
        "event_id": created_event.get("id"),
        "event_link": created_event.get("htmlLink")
    }
    
@router.get("/status")
def google_status():
        if "access_token" in TOKEN_STORE:
            return {
                "connected": True
            }
        return {
            "connected": False
        }