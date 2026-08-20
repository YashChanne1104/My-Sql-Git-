# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine

load_dotenv()


def check_db_connection(db_url: str, name: str) -> str:
    if not db_url:
        return f"{name}: DB URL is missing from .env"
    engine = create_engine(db_url)
    try:
        with engine.connect():
            return f"{name}: Database connection successful"
    except Exception as e:
        return f"{name}: Database connection failed: {e}"

