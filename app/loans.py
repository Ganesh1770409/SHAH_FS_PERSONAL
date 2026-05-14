from datetime import date
from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import LoanApplicationForm, LoanDecisionForm, RepaymentForm
from app.models import LoanApplication, Repayment

bp = Blueprint("loans", __name__, url_prefix="/loans")


@bp.route("/")
@login_required
def list_loans():
    status = request.args.get("status", "").strip()
    query = LoanApplication.query.order_by(LoanApplication.created_at.desc())
    if status in ("pending", "approved", "disbursed", "repaid", "rejected"):
        query = query.filter_by(status=status)
    return render_template("loans/list.html", loans=query.all(), filter_status=status)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_loan():
    form = LoanApplicationForm()
    if form.validate_on_submit():
        app_row = LoanApplication(
            patient_name=form.patient_name.data.strip(),
            hospital_name=form.hospital_name.data.strip(),
            ward_or_unit=(form.ward_or_unit.data or "").strip() or None,
            contact_person=form.contact_person.data.strip(),
            contact_phone=form.contact_phone.data.strip(),
            medical_summary=form.medical_summary.data.strip(),
            amount_requested=form.amount_requested.data,
            created_by_id=current_user.id,
        )
        db.session.add(app_row)
        db.session.commit()
        flash("Application saved.", "success")
        return redirect(url_for("loans.loan_detail", loan_id=app_row.id))
    return render_template("loans/new.html", form=form)


@bp.route("/<int:loan_id>")
@login_required
def loan_detail(loan_id: int):
    loan = db.session.get(LoanApplication, loan_id)
    if loan is None:
        abort(404)
    decision_form = LoanDecisionForm(obj=loan)
    decision_form.status.data = loan.status
    repayment_form = RepaymentForm()
    repayment_form.paid_on.data = date.today()
    repayments = loan.repayments.order_by(Repayment.paid_on.desc()).all()
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
    loan = db.session.get(LoanApplication, loan_id)
    if loan is None:
        abort(404)
    form = LoanDecisionForm()
    if not form.validate_on_submit():
        for err in form.errors.values():
            for e in err:
                flash(e, "danger")
        return redirect(url_for("loans.loan_detail", loan_id=loan_id))
    loan.status = form.status.data
    loan.notes = (form.notes.data or "").strip() or None
    if form.amount_approved.data is not None:
        loan.amount_approved = form.amount_approved.data
    db.session.commit()
    flash("Application updated.", "success")
    return redirect(url_for("loans.loan_detail", loan_id=loan_id))


@bp.route("/<int:loan_id>/repayment", methods=["POST"])
@login_required
def add_repayment(loan_id: int):
    loan = db.session.get(LoanApplication, loan_id)
    if loan is None:
        abort(404)
    form = RepaymentForm()
    if not form.validate_on_submit():
        for err in form.errors.values():
            for e in err:
                flash(e, "danger")
        return redirect(url_for("loans.loan_detail", loan_id=loan_id))
    rep = Repayment(loan_id=loan.id, amount=form.amount.data, paid_on=form.paid_on.data, remark=(form.remark.data or "").strip() or None)
    db.session.add(rep)
    if loan.status in ("approved", "disbursed"):
        loan.status = "disbursed"
    db.session.commit()
    flash("Repayment recorded.", "success")
    return redirect(url_for("loans.loan_detail", loan_id=loan_id))

