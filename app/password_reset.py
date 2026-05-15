"""Password-reset tokens and outbound email (Resend HTTPS or SMTP)."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage

from flask import current_app, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.db import user_get_by_id
from app.models import User

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


class MailDeliveryError(Exception):
    """Raised when outbound email fails; user_message is safe to show in the UI."""

    def __init__(self, user_message: str, *, log_detail: str = "") -> None:
        self.user_message = user_message
        super().__init__(log_detail or user_message)


def _resend_user_message(status_code: int, detail: str) -> str:
    message = detail
    try:
        payload = json.loads(detail)
        if isinstance(payload, dict):
            message = str(payload.get("message") or payload.get("error") or detail)
    except json.JSONDecodeError:
        pass

    lower = message.lower()
    if status_code == 403 and "1010" in detail:
        return "Email service blocked the request. Redeploy the latest app version and try again."
    if "only send testing emails" in lower or "verify a domain" in lower:
        return (
            "Resend test mode: you can only send to the email address on your Resend account. "
            "Sign up with that email, or verify a domain at resend.com and update MAIL_DEFAULT_SENDER."
        )
    if status_code in (401, 403):
        return "Invalid Resend API key. Set RESEND_API_KEY on Render (Environment) and redeploy."
    if message and message != detail:
        return f"Email could not be sent: {message}"
    return "We could not send the reset email. Check Render logs for details."


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


def mail_provider() -> str:
    return (current_app.config.get("MAIL_PROVIDER") or "smtp").lower().strip()


def mail_is_configured() -> bool:
    sender = current_app.config.get("MAIL_DEFAULT_SENDER")
    if not sender:
        return False
    if mail_provider() == "resend":
        return bool((current_app.config.get("RESEND_API_KEY") or "").strip())
    if os.environ.get("RENDER") == "true":
        return False
    return bool(
        current_app.config.get("MAIL_SERVER")
        and current_app.config.get("MAIL_USERNAME")
        and current_app.config.get("MAIL_PASSWORD")
    )


def _email_content(reset_url: str) -> tuple[str, str]:
    subject = "Reset your SHAH FINANCIAL HEALTH SERVICES password"
    body = (
        "You requested a password reset for your SHAH FINANCIAL HEALTH SERVICES account.\n\n"
        f"Open this link to choose a new password (expires in 1 hour):\n{reset_url}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    return subject, body


def _send_via_resend(to_email: str, subject: str, body: str) -> None:
    api_key = (current_app.config.get("RESEND_API_KEY") or "").strip()
    sender = current_app.config["MAIL_DEFAULT_SENDER"]
    payload = json.dumps(
        {"from": sender, "to": [to_email], "subject": subject, "text": body}
    ).encode("utf-8")
    req = urllib.request.Request(
        RESEND_API_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Required by Resend; urllib omits User-Agent (403 / error 1010 without it).
            "User-Agent": "shah-fs-personal/1.0 (password-reset)",
        },
    )
    timeout = int(current_app.config.get("MAIL_TIMEOUT", 15))
    logger.info("Sending password reset via Resend to=%s from=%s", to_email, sender)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status >= 400:
                body = resp.read().decode("utf-8", errors="replace")[:500]
                raise MailDeliveryError(
                    _resend_user_message(resp.status, body),
                    log_detail=f"Resend HTTP {resp.status}: {body}",
                )
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise MailDeliveryError(
            _resend_user_message(e.code, detail),
            log_detail=f"Resend HTTP {e.code}: {detail}",
        ) from e
    except urllib.error.URLError as e:
        raise MailDeliveryError(
            "Could not reach the email service. Try again in a few minutes.",
            log_detail=f"Resend connection error: {e}",
        ) from e
    logger.info("Password reset email sent via Resend to=%s", to_email)


def _send_via_smtp(to_email: str, subject: str, body: str) -> None:
    if os.environ.get("RENDER") == "true":
        raise RuntimeError(
            "SMTP is blocked on Render. Add RESEND_API_KEY to Environment (see https://resend.com)."
        )
    sender = current_app.config["MAIL_DEFAULT_SENDER"]
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(body)

    port = int(current_app.config.get("MAIL_PORT", 587))
    use_tls = current_app.config.get("MAIL_USE_TLS", True)
    username = (current_app.config.get("MAIL_USERNAME") or "").strip()
    password = (current_app.config.get("MAIL_PASSWORD") or "").strip()
    on_render = os.environ.get("RENDER") == "true"
    default_timeout = 5 if on_render else 15
    timeout = int(current_app.config.get("MAIL_TIMEOUT", default_timeout))
    server = current_app.config["MAIL_SERVER"]

    logger.info("Sending password reset via SMTP to=%s host=%s:%s", to_email, server, port)
    with smtplib.SMTP(server, port, timeout=timeout) as smtp:
        if use_tls:
            smtp.starttls()
        smtp.login(username, password)
        smtp.send_message(msg)
    logger.info("Password reset email sent via SMTP to=%s", to_email)


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    subject, body = _email_content(reset_url)
    provider = mail_provider()
    if provider == "resend":
        _send_via_resend(to_email, subject, body)
    elif provider == "smtp":
        _send_via_smtp(to_email, subject, body)
    else:
        raise ValueError(f"Unknown MAIL_PROVIDER: {provider!r} (use 'resend' or 'smtp')")
