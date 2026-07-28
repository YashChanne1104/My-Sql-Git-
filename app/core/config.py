import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DEV_DB_URL = os.getenv("DEV_DB_URL")
UAT_DB_URL = os.getenv("UAT_DB_URL")

if not DEV_DB_URL:
    raise ValueError("DEV_DB_URL is missing from .env")

if not UAT_DB_URL:
    raise ValueError("UAT_DB_URL is missing from .env")


class Settings:
    SECRET_KEY: str = os.environ["SECRET_KEY"]  # raises KeyError if missing — good
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")

settings = Settings()



FILE_PATH = Path(os.getenv("FILE_PATH", r"C:\DML SP"))

