import os
from pathlib import Path
from urllib.parse import unquote_plus, urlparse

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass


def _normalize_mysql_url(url: str) -> str:
    u = url.strip()
    if u.startswith("mysql+pymysql://"):
        return "mysql://" + u[len("mysql+pymysql://") :]
    if u.startswith("mysql://"):
        return u
    raise ValueError("DATABASE_URL must start with mysql:// or mysql+pymysql://")


def _resolve_ssl_ca() -> str | None:
    raw = os.environ.get("MYSQL_SSL_CA")
    if not raw:
        return None
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = Path(__file__).resolve().parent / p
    p = p.resolve()
    if not p.is_file():
        raise ValueError(
            f"MYSQL_SSL_CA file not found: {p}. "
            "Download AWS RDS global bundle: "
            "https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem"
        )
    return str(p)


def _apply_ssl(kw: dict) -> None:
    ca = _resolve_ssl_ca()
    if not ca:
        return
    verify_identity = os.environ.get("MYSQL_SSL_VERIFY_IDENTITY", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    kw["ssl"] = {"ca": ca}
    if verify_identity:
        # Same intent as mysql CLI --ssl-mode=VERIFY_IDENTITY
        kw["ssl"]["check_hostname"] = True


def _mysql_connection_kwargs() -> dict:
    """Build PyMySQL connect kwargs. Requires DATABASE_URL (mysql...) or MYSQL_HOST + MYSQL_USER + MYSQL_DATABASE."""
    from pymysql.cursors import DictCursor

    url = os.environ.get("DATABASE_URL") or os.environ.get("MYSQL_URL")
    if url:
        p = urlparse(_normalize_mysql_url(url))
        if not p.hostname:
            raise ValueError("MySQL URL is missing host")
        path = (p.path or "").lstrip("/")
        if not path:
            raise ValueError("MySQL URL is missing database name (path)")
        database = path.split("?")[0]
        kw: dict = {
            "host": p.hostname,
            "port": p.port or 3306,
            "user": unquote_plus(p.username or ""),
            "password": unquote_plus(p.password or ""),
            "database": database,
            "charset": "utf8mb4",
            "cursorclass": DictCursor,
            "autocommit": False,
        }
        _apply_ssl(kw)
        return kw

    host = os.environ.get("MYSQL_HOST")
    user = os.environ.get("MYSQL_USER")
    database = os.environ.get("MYSQL_DATABASE")
    if not host or not user or not database:
        raise ValueError(
            "MySQL configuration required: set DATABASE_URL (e.g. mysql+pymysql://user:pass@host:3306/dbname) "
            "or MYSQL_HOST, MYSQL_USER, MYSQL_DATABASE (and optional MYSQL_PASSWORD, MYSQL_PORT)."
        )
    kw = {
        "host": host,
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": user,
        "password": os.environ.get("MYSQL_PASSWORD", ""),
        "database": database,
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": False,
    }
    _apply_ssl(kw)
    return kw


_CONN = _mysql_connection_kwargs()
MYSQL_HOST_DISPLAY = str(_CONN.get("host") or "")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-in-production")
    MYSQL_CONN = _CONN
    MYSQL_HOST_DISPLAY = MYSQL_HOST_DISPLAY
    WTF_CSRF_TIME_LIMIT = int(os.environ.get("WTF_CSRF_TIME_LIMIT", "86400"))

    # Public site URL for password-reset links (optional; url_for _external=True if unset)
    APP_BASE_URL = (os.environ.get("APP_BASE_URL") or "").strip().rstrip("/")
    PASSWORD_RESET_MAX_AGE = int(os.environ.get("PASSWORD_RESET_MAX_AGE", "3600"))

    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")
