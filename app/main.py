from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import ProfileForm

bp = Blueprint("main", __name__)


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
