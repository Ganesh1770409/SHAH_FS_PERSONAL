from flask import Blueprint, abort, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.db import loan_counts, loan_recent, user_list_by_created_desc, user_update_profile
from app.forms import ProfileForm

bp = Blueprint("main", __name__)


def _db_kind() -> str:
    host = current_app.config.get("MYSQL_HOST_DISPLAY") or ""
    return f"MySQL ({host})" if host else "MySQL"


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/dashboard")
@login_required
def dashboard():
    stats = loan_counts()
    recent = loan_recent(8)
    return render_template(
        "dashboard.html",
        stats=stats,
        recent_loans=recent,
    )


@bp.route("/admin/users")
@login_required
def admin_users():
    if not current_user.is_admin:
        abort(403)
    users = user_list_by_created_desc()
    return render_template("admin/users.html", users=users, db_kind=_db_kind())


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        user_update_profile(
            current_user.id,
            form.full_name.data.strip(),
            (form.phone.data or "").strip() or None,
        )
        current_user.full_name = form.full_name.data.strip()
        current_user.phone = (form.phone.data or "").strip() or None
        flash("Profile updated.", "success")
        return redirect(url_for("main.profile"))
    return render_template("profile.html", form=form)
