"""Password-reset tokens and outbound email (stdlib SMTP)."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from flask import current_app, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.db import user_get_by_email
from app.models import User


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="password-reset")


def make_reset_token(user: User) -> str:
    return _serializer().dumps({"email": user.email, "pwd": user.password_hash})


def load_reset_user(token: str) -> User | None:
    max_age = int(current_app.config.get("PASSWORD_RESET_MAX_AGE", 3600))
    try:
        data = _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict):
        return None
    email = data.get("email")
    pwd = data.get("pwd")
    if not email or not pwd:
        return None
    user = user_get_by_email(str(email).lower().strip())
    if user is None or user.password_hash != pwd:
        return None
    return user


def reset_password_url(token: str) -> str:
    base = (current_app.config.get("APP_BASE_URL") or "").strip().rstrip("/")
    path = url_for("auth.reset_password", token=token)
    if base:
        return f"{base}{path}"
    return url_for("auth.reset_password", token=token, _external=True)


def mail_is_configured() -> bool:
    return bool(current_app.config.get("MAIL_SERVER") and current_app.config.get("MAIL_DEFAULT_SENDER"))


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    sender = current_app.config["MAIL_DEFAULT_SENDER"]
    subject = "Reset your SHAH FINANCIAL HEALTH SERVICES password"
    body = (
        "You requested a password reset for your SHAH FINANCIAL HEALTH SERVICES account.\n\n"
        f"Open this link to choose a new password (expires in 1 hour):\n{reset_url}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(body)

    port = int(current_app.config.get("MAIL_PORT", 587))
    use_tls = current_app.config.get("MAIL_USE_TLS", True)
    username = current_app.config.get("MAIL_USERNAME")
    password = current_app.config.get("MAIL_PASSWORD")

    with smtplib.SMTP(current_app.config["MAIL_SERVER"], port, timeout=30) as smtp:
        if use_tls:
            smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(msg)
