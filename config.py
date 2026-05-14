import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass


def _database_uri() -> str:
    # On PaaS (e.g. Render), always set DATABASE_URL to a managed Postgres (or other)
    # server DB. The default SQLite path is fine locally; on Render's ephemeral disk
    # it is recreated empty on every deploy if DATABASE_URL is missing.
    uri = os.environ.get("DATABASE_URL")
    if uri:
        if uri.startswith("postgres://"):
            uri = uri.replace("postgres://", "postgresql://", 1)
        return uri
    root = Path(__file__).resolve().parent
    db_path = (root / "hospital_loans.db").resolve()
    # Use forward slashes so the URI is valid on Windows (backslashes can break parsing).
    return "sqlite:///" + db_path.as_posix()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-in-production")
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Avoid silent login failures on an old tab after the default CSRF timeout (1 hour).
    WTF_CSRF_TIME_LIMIT = int(os.environ.get("WTF_CSRF_TIME_LIMIT", "86400"))
