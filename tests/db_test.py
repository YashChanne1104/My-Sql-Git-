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


if __name__ == "__main__":
    database_url = os.getenv("DATABASE_URL")
    dev_db_url = os.getenv("DEV_DB_URL")
    uat_db_url = os.getenv("UAT_DB_URL")

    print(check_db_connection(database_url, "DATABASE_URL"))
    print(check_db_connection(dev_db_url, "DEV_DB_URL"))
    print(check_db_connection(uat_db_url, "UAT_DB_URL"))