
from fastapi.middleware.cors import CORSMiddleware

from fastapi import FastAPI
from app.routes import classify, summarize, tasks,process,read
from app.routes import calendar
from app.routes import gmail

from app.routes import email_classifier


app = FastAPI(title="Nemo Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(gmail.router, prefix="/gmail", tags=["Gmail"])
app.include_router(email_classifier.router, tags=["Email Classification"])

app.include_router(
    classify.router,
    prefix="/classify",
    tags=["Classification"]
)

app.include_router(summarize.router, prefix="/summarize", tags=["Summarization"])

app.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])

app.include_router(process.router, prefix="/process-email", tags=["Orchestrator"])

app.include_router(read.router, tags=["Read"])

app.include_router(calendar.router, prefix="/calendar", tags=["Calendar"])



@app.get("/")
def health_check():
    return {"status": "Nemo backend running"}

