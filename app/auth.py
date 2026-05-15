from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from werkzeug.security import generate_password_hash

from app.db import user_count, user_create, user_get_by_email, user_get_by_id, user_set_password_hash
from app.forms import ForgotPasswordForm, LoginForm, ResetPasswordForm, SignupForm
from app.password_reset import (
    load_reset_user,
    mail_is_configured,
    make_reset_token,
    reset_password_url,
    send_password_reset_email,
)

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


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        user = user_get_by_email(email)
        if user is not None:
            if not mail_is_configured():
                current_app.logger.error(
                    "Password reset requested but MAIL_SERVER / MAIL_DEFAULT_SENDER are not set."
                )
            else:
                token = make_reset_token(user)
                reset_url = reset_password_url(token)
                try:
                    send_password_reset_email(user.email, reset_url)
                except Exception:
                    current_app.logger.exception("Failed to send password reset email to %s", email)
                    flash(
                        "We could not send the reset email. Try again later or contact support.",
                        "danger",
                    )
                    return render_template("auth/forgot_password.html", form=form)
        flash(
            "If an account exists for that email, you will receive a password reset link shortly.",
            "info",
        )
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    user = load_reset_user(token)
    if user is None:
        flash("This reset link is invalid or has expired. Request a new one.", "danger")
        return redirect(url_for("auth.forgot_password"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user_set_password_hash(user.id, generate_password_hash(form.password.data))
        flash("Your password has been updated. You can sign in now.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.index"))
