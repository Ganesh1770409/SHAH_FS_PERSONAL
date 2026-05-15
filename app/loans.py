from datetime import date
from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.db import (
    loan_get,
    loan_insert,
    loan_list_all_ordered,
    loan_update_decision,
    loan_set_status,
    repayment_add,
    repayments_for_loan,
)
from app.forms import LoanApplicationForm, LoanDecisionForm, RepaymentForm

bp = Blueprint("loans", __name__, url_prefix="/loans")


@bp.route("/")
@login_required
def list_loans():
    status = request.args.get("status", "").strip()
    st = status if status in ("pending", "approved", "disbursed", "repaid", "rejected") else None
    loans = loan_list_all_ordered(st)
    return render_template("loans/list.html", loans=loans, filter_status=status)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_loan():
    form = LoanApplicationForm()
    if form.validate_on_submit():
        new_id = loan_insert(
            patient_name=form.patient_name.data.strip(),
            hospital_name=form.hospital_name.data.strip(),
            ward_or_unit=(form.ward_or_unit.data or "").strip() or None,
            contact_person=form.contact_person.data.strip(),
            contact_phone=form.contact_phone.data.strip(),
            medical_summary=form.medical_summary.data.strip(),
            amount_requested=form.amount_requested.data,
            created_by_id=current_user.id,
        )
        flash("Application saved.", "success")
        return redirect(url_for("loans.loan_detail", loan_id=new_id))
    return render_template("loans/new.html", form=form)


@bp.route("/<int:loan_id>")
@login_required
def loan_detail(loan_id: int):
    loan = loan_get(loan_id)
    if loan is None:
        abort(404)
    decision_form = LoanDecisionForm(obj=loan)
    decision_form.status.data = loan.status
    repayment_form = RepaymentForm()
    repayment_form.paid_on.data = date.today()
    repayments = repayments_for_loan(loan_id)
    total_repaid = sum((r.amount for r in repayments), Decimal("0"))
    return render_template(
        "loans/detail.html",
        loan=loan,
        decision_form=decision_form,
        repayment_form=repayment_form,
        repayments=repayments,
        total_repaid=total_repaid,
    )


@bp.route("/<int:loan_id>/decision", methods=["POST"])
@login_required
def loan_decision(loan_id: int):
    loan = loan_get(loan_id)
    if loan is None:
        abort(404)
    form = LoanDecisionForm()
    if not form.validate_on_submit():
        for err in form.errors.values():
            for e in err:
                flash(e, "danger")
        return redirect(url_for("loans.loan_detail", loan_id=loan_id))
    amount_approved = form.amount_approved.data if form.amount_approved.data is not None else None
    loan_update_decision(
        loan_id,
        form.status.data,
        (form.notes.data or "").strip() or None,
        amount_approved,
    )
    flash("Application updated.", "success")
    return redirect(url_for("loans.loan_detail", loan_id=loan_id))


@bp.route("/<int:loan_id>/repayment", methods=["POST"])
@login_required
def add_repayment(loan_id: int):
    loan = loan_get(loan_id)
    if loan is None:
        abort(404)
    form = RepaymentForm()
    if not form.validate_on_submit():
        for err in form.errors.values():
            for e in err:
                flash(e, "danger")
        return redirect(url_for("loans.loan_detail", loan_id=loan_id))
    repayment_add(loan.id, form.amount.data, form.paid_on.data, (form.remark.data or "").strip() or None)
    if loan.status in ("approved", "disbursed"):
        loan_set_status(loan.id, "disbursed")
    flash("Repayment recorded.", "success")
    return redirect(url_for("loans.loan_detail", loan_id=loan_id))
