from flask import Blueprint, abort, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user

from app.db import (
    loan_counts_for_scope,
    loan_recent_for_scope,
    user_count_by_role,
    user_get_by_id,
    user_list_by_created_desc,
    user_set_role,
    user_update_profile,
)
from app.forms import AdminSetRoleForm, ProfileForm
from app.roles import sees_all_loans

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
    uid = None if sees_all_loans(current_user) else current_user.id
    stats = loan_counts_for_scope(uid)
    recent = loan_recent_for_scope(uid, 8)
    return render_template(
        "dashboard.html",
        stats=stats,
        recent_loans=recent,
        agent_scope=uid is not None,
    )


@bp.route("/admin/users")
@login_required
def admin_users():
    if not current_user.is_admin:
        abort(403)
    users = user_list_by_created_desc()
    role_form = AdminSetRoleForm()
    return render_template("admin/users.html", users=users, role_form=role_form, db_kind=_db_kind())


@bp.route("/admin/users/<int:user_id>/role", methods=["POST"])
@login_required
def admin_set_user_role(user_id: int):
    if not current_user.is_admin:
        abort(403)
    form = AdminSetRoleForm()
    if not form.validate_on_submit():
        flash("Could not update role. Refresh the page and try again.", "danger")
        return redirect(url_for("main.admin_users"))
    target = user_get_by_id(user_id)
    if target is None:
        abort(404)
    new_role = form.role.data
    if new_role == target.role:
        flash("Role is unchanged.", "info")
        return redirect(url_for("main.admin_users"))
    if target.role == "admin" and new_role != "admin" and user_count_by_role("admin") <= 1:
        flash(
            "Cannot remove the only administrator. Promote another user to admin first.",
            "danger",
        )
        return redirect(url_for("main.admin_users"))
    user_set_role(user_id, new_role)
    flash(f"Role for {target.email} set to {new_role!r}.", "success")
    if user_id == current_user.id:
        fresh = user_get_by_id(user_id)
        if fresh:
            login_user(fresh, remember=True)
    return redirect(url_for("main.admin_users"))


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
