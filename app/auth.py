import logging

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import generate_password_hash

from app.db import user_count, user_create, user_get_by_email, user_get_by_id, user_set_password_hash

logger = logging.getLogger(__name__)
from app.forms import ForgotPasswordForm, LoginForm, ResetPasswordForm, SignupForm
from app.password_reset import (
    MailDeliveryError,
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
        # First account is admin; everyone else is an agent (field staff). Promote to lender in DB if needed.
        role = "admin" if user_count() == 0 else "agent"
        email = form.email.data.lower().strip()
        full_name = form.full_name.data.strip()
        phone = (form.phone.data or "").strip() or None
        password_hash = generate_password_hash(form.password.data)
        new_id = user_create(email, password_hash, full_name, phone, role)
        login_user(user_get_by_id(new_id))
        logger.info("Signup success user_id=%s email=%s role=%s", new_id, email, role)
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
            logger.warning("Login failed for email=%s", form.email.data.lower().strip())
            flash("Invalid email or password.", "danger")
        else:
            login_user(user, remember=form.remember.data)
            logger.info("Login success user_id=%s email=%s", user.id, user.email)
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
        logger.info("Password reset requested for email=%s found=%s", email, user is not None)
        if user is not None:
            if not mail_is_configured():
                logger.error("Mail not configured: RESEND_API_KEY and MAIL_DEFAULT_SENDER required on Render")
                flash(
                    "Password reset email is not configured. Add RESEND_API_KEY on Render "
                    "(from resend.com), redeploy, then try again.",
                    "danger",
                )
                return render_template("auth/forgot_password.html", form=form)
            else:
                try:
                    token = make_reset_token(user)
                    reset_url = reset_password_url(token)
                    send_password_reset_email(user.email, reset_url)
                    logger.info("Password reset email sent user_id=%s email=%s", user.id, email)
                except MailDeliveryError as exc:
                    logger.warning("Password reset mail failed for %s: %s", email, exc)
                    flash(exc.user_message, "danger")
                    return render_template("auth/forgot_password.html", form=form)
                except Exception:
                    logger.exception("Failed to send password reset email to %s", email)
                    flash(
                        "We could not send the reset email. Check RESEND_API_KEY on Render and redeploy.",
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
        logger.warning("Invalid or expired password reset token")
        flash("This reset link is invalid or has expired. Request a new one.", "danger")
        return redirect(url_for("auth.forgot_password"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user_set_password_hash(user.id, generate_password_hash(form.password.data))
        logger.info("Password updated via reset link user_id=%s email=%s", user.id, user.email)
        flash("Your password has been updated. You can sign in now.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logger.info("Logout user_id=%s", current_user.id)
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.index"))
