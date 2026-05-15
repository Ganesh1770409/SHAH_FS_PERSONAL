from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import login_manager


def _coerce_datetime(v) -> datetime:
    if isinstance(v, datetime):
        return v.replace(tzinfo=None) if v.tzinfo else v
    if isinstance(v, str):
        s = v.strip().replace(" ", "T", 1)
        return datetime.fromisoformat(s[:26].split("+")[0])
    raise TypeError(f"expected datetime-like value, got {type(v)!r}")


def _coerce_money(v) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _coerce_money_nonnull(v) -> Decimal:
    x = _coerce_money(v)
    return x if x is not None else Decimal("0")


def _coerce_date(v) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


class User(UserMixin):
    __slots__ = ("id", "email", "password_hash", "full_name", "phone", "role", "created_at")

    def __init__(
        self,
        id: int,
        email: str,
        password_hash: str,
        full_name: str,
        phone: str | None,
        role: str,
        created_at: datetime,
    ):
        self.id = id
        self.email = email
        self.password_hash = password_hash
        self.full_name = full_name
        self.phone = phone
        self.role = role
        self.created_at = created_at

    @classmethod
    def from_row(cls, row) -> "User":
        return cls(
            id=row["id"],
            email=row["email"],
            password_hash=row["password_hash"],
            full_name=row["full_name"],
            phone=row["phone"],
            role=row["role"],
            created_at=_coerce_datetime(row["created_at"]),
        )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


@login_manager.user_loader
def load_user(user_id: str):
    from app.db import user_get_by_id

    return user_get_by_id(int(user_id))


@dataclass
class Loan:
    id: int
    patient_name: str
    hospital_name: str
    ward_or_unit: str | None
    contact_person: str
    contact_phone: str
    medical_summary: str
    amount_requested: Decimal
    amount_approved: Decimal | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
    created_by_id: int
    created_by_user: User | None = None

    @classmethod
    def from_row(cls, row) -> "Loan":
        return cls(
            id=row["id"],
            patient_name=row["patient_name"],
            hospital_name=row["hospital_name"],
            ward_or_unit=row["ward_or_unit"],
            contact_person=row["contact_person"],
            contact_phone=row["contact_phone"],
            medical_summary=row["medical_summary"],
            amount_requested=_coerce_money_nonnull(row["amount_requested"]),
            amount_approved=_coerce_money(row["amount_approved"]),
            status=row["status"],
            notes=row["notes"],
            created_at=_coerce_datetime(row["created_at"]),
            updated_at=_coerce_datetime(row["updated_at"]),
            created_by_id=row["created_by_id"],
            created_by_user=None,
        )


@dataclass
class Repayment:
    id: int
    loan_id: int
    amount: Decimal
    paid_on: date
    recorded_at: datetime
    remark: str | None

    @classmethod
    def from_row(cls, row) -> "Repayment":
        return cls(
            id=row["id"],
            loan_id=row["loan_id"],
            amount=_coerce_money_nonnull(row["amount"]),
            paid_on=_coerce_date(row["paid_on"]),
            recorded_at=_coerce_datetime(row["recorded_at"]),
            remark=row["remark"],
        )
