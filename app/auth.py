from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.forms import LoginForm, SignupForm
from app.models import User

bp = Blueprint("auth", __name__, url_prefix="")


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = SignupForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data.lower().strip(),
            full_name=form.full_name.data.strip(),
            phone=(form.phone.data or "").strip() or None,
        )
        user.set_password(form.password.data)
        if User.query.count() == 0:
            user.role = "admin"
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Your account is ready. Welcome.", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("auth/signup.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user is None or not user.check_password(form.password.data):
            flash("Invalid email or password.", "danger")
        else:
            login_user(user, remember=form.remember.data)
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect(url_for("main.dashboard"))
    return render_template("auth/login.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.index"))
