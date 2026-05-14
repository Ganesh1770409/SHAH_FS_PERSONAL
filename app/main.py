from flask import Blueprint, abort, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import ProfileForm
from app.models import User

bp = Blueprint("main", __name__)


def _db_kind() -> str:
    uri = (current_app.config.get("SQLALCHEMY_DATABASE_URI") or "").lower()
    if uri.startswith("sqlite"):
        return "SQLite"
    if "mysql" in uri:
        return "MySQL"
    if uri.startswith("postgresql"):
        return "PostgreSQL"
    return "SQL"


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/dashboard")
@login_required
def dashboard():
    from app.models import LoanApplication

    q = LoanApplication.query
    total = q.count()
    pending = q.filter_by(status="pending").count()
    approved = q.filter(LoanApplication.status.in_(["approved", "disbursed"])).count()
    repaid = q.filter_by(status="repaid").count()
    recent = q.order_by(LoanApplication.created_at.desc()).limit(8).all()
    return render_template(
        "dashboard.html",
        stats={"total": total, "pending": pending, "approved": approved, "repaid": repaid},
        recent_loans=recent,
    )


@bp.route("/admin/users")
@login_required
def admin_users():
    """List users from the live DB (admin only). Use on Render to confirm signups hit Postgres."""
    if not current_user.is_admin:
        abort(403)
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users, db_kind=_db_kind())


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.full_name = form.full_name.data.strip()
        current_user.phone = (form.phone.data or "").strip() or None
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("main.profile"))
    return render_template("profile.html", form=form)
