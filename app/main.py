from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from .core.config import DEV_DB_URL, UAT_DB_URL
# pyrefly: ignore [missing-import]
from .models import models          # <-- must import the models module directly
from .core.database import Base, engine
from tests.db_test import check_db_connection
from app.routers import sql_review
from app.services.classifier import classify_sql
from app.routers import submissions
from app.routers import admin
from app.routers import login
from .core import auth
from app.routers import audit_router
from fastapi.staticfiles import StaticFiles
from app.routers import pages
 

app = FastAPI(title="SQL Deploy Gate", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
 
app.include_router(pages.router)
 
Base.metadata.create_all(bind=engine)   # <-- must run AFTER the imports above
 
app.include_router(sql_review.router)
app.include_router(submissions.router)
app.include_router(login.router)
app.include_router(admin.router)
app.include_router(audit_router.router)
 
 
class SQLSubmission(BaseModel):
    sql_text: str
 
 
@app.get("/", response_class=HTMLResponse)
def root(request: Request, current_user: models.User | None = Depends(auth.get_current_user_optional)):
    return templates.TemplateResponse("home.html", {"request": request, "current_user": current_user})
 
 
@app.get("/health/connections")
def check_connections():
    return {
        "dev": check_db_connection(DEV_DB_URL, "DEV"),
        "uat": check_db_connection(UAT_DB_URL, "UAT"),
    }
 
 
@app.post("/classify")
def classify(submission: SQLSubmission):
    return classify_sql(submission.sql_text)
 