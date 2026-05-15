from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, DecimalField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional, ValidationError

from app.db import user_email_exists


class SignupForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), Length(max=32)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password", message="Passwords must match.")])
    submit = SubmitField("Create account")

    def validate_email(self, field):
        if user_email_exists(field.data.lower().strip()):
            raise ValidationError("An account with this email already exists.")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")
    submit = SubmitField("Sign in")


class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    submit = SubmitField("Send reset link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm = PasswordField(
        "Confirm new password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Update password")


class LoanApplicationForm(FlaskForm):
    patient_name = StringField("Patient name", validators=[DataRequired(), Length(max=120)])
    hospital_name = StringField("Hospital / facility", validators=[DataRequired(), Length(max=200)])
    ward_or_unit = StringField("Ward or unit", validators=[Optional(), Length(max=120)])
    contact_person = StringField("Contact person (family / coordinator)", validators=[DataRequired(), Length(max=120)])
    contact_phone = StringField("Contact phone", validators=[DataRequired(), Length(max=32)])
    medical_summary = TextAreaField("Situation & how funds will help", validators=[DataRequired(), Length(min=20, max=4000)])
    amount_requested = DecimalField("Amount requested", validators=[DataRequired(), NumberRange(min=Decimal("1"))], places=2)
    submit = SubmitField("Submit application")


class LoanDecisionForm(FlaskForm):
    status = SelectField(
        "Status",
        choices=[
            ("pending", "Pending review"),
            ("approved", "Approved"),
            ("disbursed", "Disbursed"),
            ("repaid", "Fully repaid"),
            ("rejected", "Rejected"),
        ],
        validators=[DataRequired()],
    )
    amount_approved = DecimalField("Approved amount (if applicable)", validators=[Optional(), NumberRange(min=Decimal("0"))], places=2)
    notes = TextAreaField("Internal notes", validators=[Optional(), Length(max=4000)])
    submit = SubmitField("Save")


class RepaymentForm(FlaskForm):
    amount = DecimalField("Amount received", validators=[DataRequired(), NumberRange(min=Decimal("0.01"))], places=2)
    paid_on = DateField("Payment date", validators=[DataRequired()], format="%Y-%m-%d")
    remark = StringField("Remark", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Record repayment")


class ProfileForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), Length(max=32)])
    submit = SubmitField("Update profile")
