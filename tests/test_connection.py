# pyrefly: ignore [missing-import]
from sqlalchemy import text

from app.core.database import engine
with engine.connect() as conn:
    result = conn.execute(text("SELECT version();"))
    print("Connected! Postgres version:", result.fetchone())