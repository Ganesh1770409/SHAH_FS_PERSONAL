"""MySQL persistence via PyMySQL (raw SQL, no ORM)."""
from __future__ import annotations

import logging
import re
from contextlib import contextmanager

logger = logging.getLogger(__name__)
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pymysql
import pymysql.err
from flask import current_app

_DB_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _utc_now() -> datetime:
    return datetime.utcnow().replace(microsecond=0)


@contextmanager
def get_conn() -> Any:
    conn = pymysql.connect(**current_app.config["MYSQL_CONN"])
    try:
        yield conn
    finally:
        conn.close()


def ensure_database() -> None:
    """Create MYSQL_DATABASE / DATABASE_URL path if missing (avoids MySQL 1049 on first deploy)."""
    cfg = dict(current_app.config["MYSQL_CONN"])
    db_name = cfg.pop("database", None)
    if not db_name:
        return
    if not _DB_NAME_RE.fullmatch(db_name):
        raise ValueError(f"Invalid MySQL database name: {db_name!r}")
    conn = pymysql.connect(**cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
        logger.info("Database ensured: %s", db_name)
    finally:
        conn.close()


def init_db() -> None:
    logger.debug("Initializing database schema")
    ensure_database()
    ddl = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(120) NOT NULL,
            password_hash VARCHAR(256) NOT NULL,
            full_name VARCHAR(120) NOT NULL,
            phone VARCHAR(32) NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'lender',
            created_at DATETIME NOT NULL,
            UNIQUE KEY uq_users_email (email)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS loan_applications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            patient_name VARCHAR(120) NOT NULL,
            hospital_name VARCHAR(200) NOT NULL,
            ward_or_unit VARCHAR(120) NULL,
            contact_person VARCHAR(120) NOT NULL,
            contact_phone VARCHAR(32) NOT NULL,
            medical_summary TEXT NOT NULL,
            amount_requested DECIMAL(12, 2) NOT NULL,
            amount_approved DECIMAL(12, 2) NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            notes TEXT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            created_by_id INT NOT NULL,
            CONSTRAINT fk_loans_user FOREIGN KEY (created_by_id) REFERENCES users (id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS repayments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            loan_id INT NOT NULL,
            amount DECIMAL(12, 2) NOT NULL,
            paid_on DATE NOT NULL,
            recorded_at DATETIME NOT NULL,
            remark VARCHAR(255) NULL,
            CONSTRAINT fk_repayments_loan FOREIGN KEY (loan_id) REFERENCES loan_applications (id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
    ]
    index_sql = [
        "CREATE INDEX idx_loans_status ON loan_applications (status)",
        "CREATE INDEX idx_loans_created ON loan_applications (created_at)",
    ]
    with get_conn() as conn:
        with conn.cursor() as cur:
            for stmt in ddl:
                cur.execute(stmt)
            for sql in index_sql:
                try:
                    cur.execute(sql)
                except pymysql.err.OperationalError as e:
                    if e.args[0] != 1061 and "Duplicate" not in str(e):
                        raise
        conn.commit()


def verify_connection() -> tuple[str, str]:
    """Ping MySQL; return (host, database) for startup logs."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE() AS db")
            row = cur.fetchone()
    cfg = current_app.config["MYSQL_CONN"]
    return str(cfg.get("host") or ""), str(row["db"] or cfg.get("database") or "")


def _dec_str(v: Decimal | None) -> Any:
    if v is None:
        return None
    return v


def user_count() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM users")
            row = cur.fetchone()
            return int(row["c"])


def user_email_exists(email: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS x FROM users WHERE email = %s LIMIT 1", (email,))
            return cur.fetchone() is not None


def user_create(email: str, password_hash: str, full_name: str, phone: str | None, role: str) -> int:
    now = _utc_now()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (email, password_hash, full_name, phone, role, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (email, password_hash, full_name, phone, role, now),
            )
            new_id = int(cur.lastrowid)
        conn.commit()
        return new_id


def user_get_by_id(user_id: int):
    from app.models import User

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
    return User.from_row(row) if row else None


def user_get_by_email(email: str):
    from app.models import User

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            row = cur.fetchone()
    return User.from_row(row) if row else None


def user_list_by_created_desc():
    from app.models import User

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users ORDER BY created_at DESC")
            rows = cur.fetchall()
    return [User.from_row(r) for r in rows]


def user_update_profile(user_id: int, full_name: str, phone: str | None) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET full_name = %s, phone = %s WHERE id = %s",
                (full_name, phone, user_id),
            )
        conn.commit()


def user_set_password_hash(user_id: int, password_hash: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))
        conn.commit()


ROLE_AGENT = "agent"
ROLE_LENDER = "lender"
ROLE_ADMIN = "admin"
_VALID_ROLES = frozenset({ROLE_AGENT, ROLE_LENDER, ROLE_ADMIN})


def user_count_by_role(role: str) -> int:
    if role not in _VALID_ROLES:
        raise ValueError("Invalid role")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM users WHERE role = %s", (role,))
            return int(cur.fetchone()["c"])


def user_set_role(user_id: int, role: str) -> None:
    if role not in _VALID_ROLES:
        raise ValueError(f"Invalid role: {role!r}")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET role = %s WHERE id = %s", (role, user_id))
        conn.commit()


def loan_insert(
    *,
    patient_name: str,
    hospital_name: str,
    ward_or_unit: str | None,
    contact_person: str,
    contact_phone: str,
    medical_summary: str,
    amount_requested: Decimal,
    created_by_id: int,
) -> int:
    now = _utc_now()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO loan_applications (
                    patient_name, hospital_name, ward_or_unit, contact_person, contact_phone,
                    medical_summary, amount_requested, amount_approved, status, notes,
                    created_at, updated_at, created_by_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, 'pending', NULL, %s, %s, %s)
                """,
                (
                    patient_name,
                    hospital_name,
                    ward_or_unit,
                    contact_person,
                    contact_phone,
                    medical_summary,
                    _dec_str(amount_requested),
                    now,
                    now,
                    created_by_id,
                ),
            )
            new_id = int(cur.lastrowid)
        conn.commit()
        return new_id


def loan_get(loan_id: int):
    from app.models import Loan, User

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM loan_applications WHERE id = %s", (loan_id,))
            row = cur.fetchone()
            if row is None:
                return None
            cur.execute("SELECT * FROM users WHERE id = %s", (row["created_by_id"],))
            urow = cur.fetchone()
    loan = Loan.from_row(row)
    loan.created_by_user = User.from_row(urow) if urow else None
    return loan


def loan_list_all_ordered(status: str | None = None):
    return loan_list_for_scope(None, status)


def loan_list_for_scope(created_by_user_id: int | None, status: str | None = None):
    from app.models import Loan

    with get_conn() as conn:
        with conn.cursor() as cur:
            clauses: list[str] = []
            args: list[Any] = []
            if created_by_user_id is not None:
                clauses.append("created_by_id = %s")
                args.append(created_by_user_id)
            if status in ("pending", "approved", "disbursed", "repaid", "rejected"):
                clauses.append("status = %s")
                args.append(status)
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            cur.execute(
                f"SELECT * FROM loan_applications{where} ORDER BY created_at DESC",
                tuple(args),
            )
            rows = cur.fetchall()
    return [Loan.from_row(r) for r in rows]


def loan_update_decision(loan_id: int, status: str, notes: str | None, amount_approved: Decimal | None) -> None:
    now = _utc_now()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE loan_applications
                SET status = %s, notes = %s, amount_approved = %s, updated_at = %s
                WHERE id = %s
                """,
                (status, notes, _dec_str(amount_approved), now, loan_id),
            )
        conn.commit()


def loan_set_status(loan_id: int, status: str) -> None:
    now = _utc_now()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE loan_applications SET status = %s, updated_at = %s WHERE id = %s",
                (status, now, loan_id),
            )
        conn.commit()


def repayments_for_loan(loan_id: int):
    from app.models import Repayment

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM repayments WHERE loan_id = %s ORDER BY paid_on DESC, id DESC",
                (loan_id,),
            )
            rows = cur.fetchall()
    return [Repayment.from_row(r) for r in rows]


def repayment_add(loan_id: int, amount: Decimal, paid_on: date, remark: str | None) -> None:
    now = _utc_now()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO repayments (loan_id, amount, paid_on, recorded_at, remark)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (loan_id, _dec_str(amount), paid_on, now, remark),
            )
        conn.commit()


def loan_counts() -> dict[str, int]:
    return loan_counts_for_scope(None)


def loan_counts_for_scope(created_by_user_id: int | None) -> dict[str, int]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            if created_by_user_id is None:
                cur.execute("SELECT COUNT(*) AS c FROM loan_applications")
                total = int(cur.fetchone()["c"])
                cur.execute("SELECT COUNT(*) AS c FROM loan_applications WHERE status = 'pending'")
                pending = int(cur.fetchone()["c"])
                cur.execute(
                    "SELECT COUNT(*) AS c FROM loan_applications WHERE status IN ('approved', 'disbursed')"
                )
                approved = int(cur.fetchone()["c"])
                cur.execute("SELECT COUNT(*) AS c FROM loan_applications WHERE status = 'repaid'")
                repaid = int(cur.fetchone()["c"])
            else:
                uid = created_by_user_id
                cur.execute(
                    "SELECT COUNT(*) AS c FROM loan_applications WHERE created_by_id = %s",
                    (uid,),
                )
                total = int(cur.fetchone()["c"])
                cur.execute(
                    "SELECT COUNT(*) AS c FROM loan_applications WHERE created_by_id = %s AND status = 'pending'",
                    (uid,),
                )
                pending = int(cur.fetchone()["c"])
                cur.execute(
                    "SELECT COUNT(*) AS c FROM loan_applications WHERE created_by_id = %s AND status IN ('approved', 'disbursed')",
                    (uid,),
                )
                approved = int(cur.fetchone()["c"])
                cur.execute(
                    "SELECT COUNT(*) AS c FROM loan_applications WHERE created_by_id = %s AND status = 'repaid'",
                    (uid,),
                )
                repaid = int(cur.fetchone()["c"])
    return {"total": total, "pending": pending, "approved": approved, "repaid": repaid}


def loan_recent(limit: int = 8):
    return loan_recent_for_scope(None, limit)


def loan_recent_for_scope(created_by_user_id: int | None, limit: int = 8):
    from app.models import Loan

    with get_conn() as conn:
        with conn.cursor() as cur:
            if created_by_user_id is None:
                cur.execute(
                    "SELECT * FROM loan_applications ORDER BY created_at DESC LIMIT %s",
                    (int(limit),),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM loan_applications
                    WHERE created_by_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (created_by_user_id, int(limit)),
                )
            rows = cur.fetchall()
    return [Loan.from_row(r) for r in rows]
