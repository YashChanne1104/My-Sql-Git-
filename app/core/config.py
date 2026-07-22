import os
from dotenv import load_dotenv

load_dotenv()

DEV_DB_URL = os.getenv("DEV_DB_URL")
UAT_DB_URL = os.getenv("UAT_DB_URL")

if not DEV_DB_URL:
    raise ValueError("DEV_DB_URL is missing from .env")

if not UAT_DB_URL:
    raise ValueError("UAT_DB_URL is missing from .env")