import os
from pathlib import Path
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

class Settings:
    SECRET_KEY: str = os.environ["SECRET_KEY"]
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
    DATABASE_URL: str = os.environ["DATABASE_URL"]  # no silent SQLite fallback

settings = Settings()

FILE_PATH = Path(os.getenv("FILE_PATH", r"C:\DML SP"))