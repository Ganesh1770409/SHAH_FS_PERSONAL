from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from werkzeug.security import generate_password_hash

from app.db import user_count, user_create, user_get_by_email, user_get_by_id
from app.forms import LoginForm, SignupForm

bp = Blueprint("auth", __name__, url_prefix="")


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = SignupForm()
    if form.validate_on_submit():
        role = "admin" if user_count() == 0 else "lender"
        email = form.email.data.lower().strip()
        full_name = form.full_name.data.strip()
        phone = (form.phone.data or "").strip() or None
        password_hash = generate_password_hash(form.password.data)
        new_id = user_create(email, password_hash, full_name, phone, role)
        login_user(user_get_by_id(new_id))
        flash("Your account is ready. Welcome.", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("auth/signup.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        user = user_get_by_email(form.email.data.lower().strip())
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
