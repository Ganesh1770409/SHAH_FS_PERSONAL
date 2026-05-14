from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(32))
    role = db.Column(db.String(20), nullable=False, default="lender")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    loan_applications = db.relationship("LoanApplication", backref="created_by_user", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


class LoanApplication(db.Model):
    __tablename__ = "loan_applications"

    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(120), nullable=False)
    hospital_name = db.Column(db.String(200), nullable=False)
    ward_or_unit = db.Column(db.String(120))
    contact_person = db.Column(db.String(120), nullable=False)
    contact_phone = db.Column(db.String(32), nullable=False)
    medical_summary = db.Column(db.Text, nullable=False)
    amount_requested = db.Column(db.Numeric(12, 2), nullable=False)
    amount_approved = db.Column(db.Numeric(12, 2))
    status = db.Column(db.String(20), nullable=False, default="pending")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    repayments = db.relationship("Repayment", backref="loan", lazy="dynamic", cascade="all, delete-orphan")


class Repayment(db.Model):
    __tablename__ = "repayments"

    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey("loan_applications.id"), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    paid_on = db.Column(db.Date, nullable=False)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    remark = db.Column(db.String(255))
