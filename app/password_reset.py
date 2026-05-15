"""Password-reset tokens and outbound email (stdlib SMTP)."""
from __future__ import annotations

import hashlib
import logging
import smtplib

logger = logging.getLogger(__name__)
from email.message import EmailMessage

from flask import current_app, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.db import user_get_by_id
from app.models import User


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="password-reset")


def _password_sig(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:32]


def make_reset_token(user: User) -> str:
    return _serializer().dumps({"uid": user.id, "sig": _password_sig(user.password_hash)})


def load_reset_user(token: str) -> User | None:
    max_age = int(current_app.config.get("PASSWORD_RESET_MAX_AGE", 3600))
    try:
        data = _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict):
        return None
    uid = data.get("uid")
    sig = data.get("sig")
    if uid is None or not sig:
        return None
    try:
        user_id = int(uid)
    except (TypeError, ValueError):
        return None
    user = user_get_by_id(user_id)
    if user is None or _password_sig(user.password_hash) != sig:
        return None
    return user


def reset_password_url(token: str) -> str:
    base = (current_app.config.get("APP_BASE_URL") or "").strip().rstrip("/")
    path = url_for("auth.reset_password", token=token)
    if base:
        return f"{base}{path}"
    return url_for("auth.reset_password", token=token, _external=True)


def mail_is_configured() -> bool:
    return bool(
        current_app.config.get("MAIL_SERVER")
        and current_app.config.get("MAIL_DEFAULT_SENDER")
        and current_app.config.get("MAIL_USERNAME")
        and current_app.config.get("MAIL_PASSWORD")
    )


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
    username = (current_app.config.get("MAIL_USERNAME") or "").strip()
    password = (current_app.config.get("MAIL_PASSWORD") or "").strip()
    timeout = int(current_app.config.get("MAIL_TIMEOUT", 15))

    server = current_app.config["MAIL_SERVER"]
    logger.info("Sending password reset email to=%s via %s:%s", to_email, server, port)
    with smtplib.SMTP(server, port, timeout=timeout) as smtp:
        if use_tls:
            smtp.starttls()
        smtp.login(username, password)
        smtp.send_message(msg)
    logger.info("Password reset email delivered to=%s", to_email)
