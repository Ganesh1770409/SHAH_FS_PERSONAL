import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass


def _normalize_database_uri(uri: str) -> str:
    """Make SQLAlchemy-compatible URIs from common host-provided strings."""
    uri = uri.strip()
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)
    # Plain mysql:// defaults to PyMySQL driver (pure Python, works on Windows).
    if uri.startswith("mysql://") and not uri.startswith("mysql+pymysql://"):
        uri = uri.replace("mysql://", "mysql+pymysql://", 1)
    return uri


def _database_uri() -> str:
    """
    Prefer DATABASE_URL (MySQL, PostgreSQL, etc.). If unset, use local SQLite.

    MySQL example:
      DATABASE_URL=mysql+pymysql://USER:PASS@HOST:3306/DBNAME?charset=utf8mb4

    On PaaS without DATABASE_URL, SQLite lives on ephemeral disk and is wiped on redeploy.
    """
    uri = os.environ.get("DATABASE_URL")
    if uri:
        return _normalize_database_uri(uri)
    root = Path(__file__).resolve().parent
    db_path = (root / "hospital_loans.db").resolve()
    return "sqlite:///" + db_path.as_posix()


def _engine_options(uri: str) -> dict:
    """Connection pool hints for long-lived servers (especially MySQL idle timeouts)."""
    if "mysql" in uri.lower():
        return {"pool_pre_ping": True, "pool_recycle": 280}
    return {}


_URI = _database_uri()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-in-production")
    SQLALCHEMY_DATABASE_URI = _URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options(_URI)
    WTF_CSRF_TIME_LIMIT = int(os.environ.get("WTF_CSRF_TIME_LIMIT", "86400"))
