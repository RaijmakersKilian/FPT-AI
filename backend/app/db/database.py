import os

import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in .env")


def get_database_url() -> str:
    if "sslmode=" not in DATABASE_URL:
        separator = "&" if "?" in DATABASE_URL else "?"
        return f"{DATABASE_URL}{separator}sslmode=require"

    return DATABASE_URL


def get_connection():
    return psycopg.connect(get_database_url())