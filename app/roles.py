"""Role-based access: agent (submit), lender (approve/repay), admin (all + users)."""
from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Callable

from flask import abort, flash, redirect, url_for
from flask_login import current_user, login_required

if TYPE_CHECKING:
    from app.models import User


def lenders_and_admins_only():
    """Lender or admin: full portfolio, decisions, repayments."""
    return current_user.is_authenticated and (
        current_user.is_lender or current_user.is_admin
    )


def agents_and_admins_only():
    """Agent or admin: can submit new applications."""
    return current_user.is_authenticated and (current_user.is_agent or current_user.is_admin)


def sees_all_loans(user: User) -> bool:
    return user.is_lender or user.is_admin


def can_create_application(user: User) -> bool:
    return user.is_agent or user.is_admin


def can_decide_loans(user: User) -> bool:
    return user.is_lender or user.is_admin


def can_record_repayments(user: User) -> bool:
    return user.is_lender or user.is_admin


def can_access_admin_pages(user: User) -> bool:
    return user.is_admin


def can_view_loan(user: User, loan) -> bool:
    """Loan model must have created_by_id."""
    if sees_all_loans(user):
        return True
    return loan.created_by_id == user.id


def require_roles(*allowed: str):
    """Decorator: allow only users whose role is in allowed (e.g. 'lender', 'admin')."""

    def decorator(view: Callable):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in allowed:
                flash("You do not have access to that page.", "danger")
                return redirect(url_for("main.dashboard"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def require_lender_or_admin(view: Callable):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not lenders_and_admins_only():
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def require_agent_or_admin(view: Callable):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not agents_and_admins_only():
            abort(403)
        return view(*args, **kwargs)

    return wrapped
