from fastapi import FastAPI
from pydantic import BaseModel
 
from .core.config import DEV_DB_URL, UAT_DB_URL
# pyrefly: ignore [missing-import]
from tests.db_test import check_db_connection
from app.routers import sql_review
from app.services.classifier import classify_sql
from app.routers import approval
 
app = FastAPI(title="SQL Deploy Gate", version="0.1.0")
app.include_router(sql_review.router)
app.include_router(approval.router)

class SQLSubmission(BaseModel):
    sql_text: str


@app.get("/")
def root():
    return {"status": "running", "service": "SQL Deploy Gate"}


@app.get("/health/connections")
def check_connections():
    return {
        "dev": check_db_connection(DEV_DB_URL, "DEV"),
        "uat": check_db_connection(UAT_DB_URL, "UAT"),
    }


@app.post("/classify")
def classify(submission: SQLSubmission):
    result = classify_sql(submission.sql_text)
    return result