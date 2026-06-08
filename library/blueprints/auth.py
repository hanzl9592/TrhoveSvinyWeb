import secrets
from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask import current_app
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from sqlalchemy.exc import SQLAlchemyError
from wtforms import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length

from .. import db
from ..email_service import send_mailtrap_email, send_verification_email
from ..i18n import tr
from ..models import User

bp = Blueprint("auth", __name__)


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign in")


class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(3, 64)])
    first_name = StringField("First name", validators=[DataRequired(), Length(1, 80)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(1, 80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(6, 120)])
    password = PasswordField("Password", validators=[DataRequired(), Length(6, 128)])
    confirm = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match")],
    )
    submit = SubmitField("Create account")


class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(6, 120)])
    submit = SubmitField("Send reset link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("Password", validators=[DataRequired(), Length(6, 128)])
    confirm = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match")],
    )
    submit = SubmitField("Set new password")


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


def _token_expired(expires_at: datetime | None) -> bool:
    if not expires_at:
        return True
    return datetime.utcnow() > expires_at


def _send_plain_email(to_email: str, subject: str, body: str) -> bool:
    ok, code, detail = send_mailtrap_email(
        to_email=to_email,
        subject=subject,
        text=body,
        category="Integration Test",
    )
    if ok:
        current_app.logger.info("Mail send success [%s] to=%s detail=%s", code, to_email, detail)
        return True

    current_app.logger.warning("Mail send failed [%s] to=%s detail=%s", code, to_email, detail)
    return False


def _send_verification_email(to_email: str, verify_link: str) -> bool:
    ok, code, detail = send_verification_email(
        to_email=to_email,
        verify_link=verify_link,
        subject=tr("auth.verify_subject"),
    )
    if ok:
        current_app.logger.info("Verification send success [%s] to=%s detail=%s", code, to_email, detail)
        return True

    current_app.logger.warning("Verification send failed [%s] to=%s detail=%s", code, to_email, detail)
    return False


def _send_password_reset_email(to_email: str, reset_link: str) -> bool:
    return _send_plain_email(
        to_email=to_email,
        subject=tr("auth.reset_subject"),
        body=(
            f"{tr('auth.reset_mail_intro')}\n\n"
            f"{tr('auth.reset_mail_cta')}\n"
            f"{reset_link}\n"
        ),
    )


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = LoginForm()
    if form.validate_on_submit():
        username = (form.username.data or "").strip()
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(form.password.data):
            if not user.is_email_verified:
                if _token_expired(user.email_verification_expires_at):
                    user.email_verification_token = _generate_token()
                    ttl_hours = int(
                        current_app.config.get("EMAIL_VERIFICATION_TOKEN_TTL_HOURS", 24)
                    )
                    user.email_verification_expires_at = datetime.utcnow() + timedelta(
                        hours=ttl_hours
                    )
                    db.session.commit()
                verify_link = url_for(
                    "auth.verify_email",
                    token=user.email_verification_token,
                    _external=True,
                )
                if _send_verification_email(user.email, verify_link):
                    flash(tr("auth.verify_email_sent"), "info")
                else:
                    flash(tr("auth.verify_email_fallback", link=verify_link), "warning")
                flash(tr("auth.verify_email_needed"), "warning")
                return redirect(url_for("auth.login"))

            login_user(user)
            flash(tr("auth.welcome_back"), "success")
            next_url = request.args.get("next")
            if next_url:
                return redirect(next_url)
            if user.is_admin:
                flash(tr("auth.admin_mode"), "info")
            return redirect(url_for("catalog.index"))
        flash(tr("auth.invalid_credentials"), "danger")
    return render_template("auth/login.html", form=form)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = RegisterForm()
    try:
        if form.validate_on_submit():
            username = (form.username.data or "").strip()
            first_name = (form.first_name.data or "").strip()
            last_name = (form.last_name.data or "").strip()
            email = (form.email.data or "").strip().lower()

            if User.query.filter_by(username=username).first():
                flash(tr("auth.username_taken"), "warning")
            elif User.query.filter_by(email=email).first():
                flash(tr("auth.email_taken"), "warning")
            else:
                token = _generate_token()
                ttl_hours = int(current_app.config.get("EMAIL_VERIFICATION_TOKEN_TTL_HOURS", 24))
                user = User(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    role="student",
                    is_email_verified=False,
                    email_verification_token=token,
                    email_verification_expires_at=datetime.utcnow() + timedelta(hours=ttl_hours),
                )
                user.set_password(form.password.data)
                db.session.add(user)
                try:
                    db.session.commit()
                except SQLAlchemyError:
                    db.session.rollback()
                    current_app.logger.exception("Registration failed at DB commit [REG-DB-01]")
                    flash(tr("auth.account_create_failed", code="REG-DB-01"), "danger")
                    return render_template("auth/register.html", form=form)

                try:
                    verify_link = url_for("auth.verify_email", token=token, _external=True)
                    if _send_verification_email(email, verify_link):
                        flash(tr("auth.verify_email_sent"), "success")
                    else:
                        flash(tr("auth.verify_email_fallback", link=verify_link), "warning")
                        flash(tr("auth.verify_email_issue", code="REG-MAIL-01"), "warning")

                    flash(tr("auth.account_created"), "success")
                    return redirect(url_for("auth.login"))
                except Exception:
                    # Account is already created; only the follow-up step failed.
                    current_app.logger.exception(
                        "Registration completed but follow-up failed [REG-AFTER-01]"
                    )
                    flash(tr("auth.account_created"), "success")
                    flash(tr("auth.registration_followup_issue", code="REG-AFTER-01"), "warning")
                    return redirect(url_for("auth.login"))
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Unhandled registration exception [REG-UNHANDLED-01]")
        flash(tr("auth.registration_unhandled", code="REG-UNHANDLED-01"), "danger")
    return render_template("auth/register.html", form=form)


@bp.route("/verify-email/<token>")
def verify_email(token: str):
    user = User.query.filter_by(email_verification_token=token).first()
    if not user or _token_expired(user.email_verification_expires_at):
        flash(tr("auth.verify_invalid"), "warning")
        return redirect(url_for("auth.login"))

    user.is_email_verified = True
    user.email_verification_token = None
    user.email_verification_expires_at = None
    db.session.commit()
    flash(tr("auth.verify_success"), "success")
    return redirect(url_for("auth.login"))


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = (form.email.data or "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = _generate_token()
            ttl_hours = int(current_app.config.get("PASSWORD_RESET_TOKEN_TTL_HOURS", 2))
            user.password_reset_token = token
            user.password_reset_expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
            db.session.commit()

            reset_link = url_for("auth.reset_password", token=token, _external=True)
            if _send_password_reset_email(email, reset_link):
                flash(tr("auth.reset_email_sent"), "success")
            else:
                flash(tr("auth.reset_email_fallback", link=reset_link), "warning")
        else:
            flash(tr("auth.reset_email_sent"), "success")

        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    user = User.query.filter_by(password_reset_token=token).first()
    if not user or _token_expired(user.password_reset_expires_at):
        flash(tr("auth.reset_invalid"), "warning")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.password_reset_token = None
        user.password_reset_expires_at = None
        db.session.commit()
        flash(tr("auth.reset_success"), "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash(tr("auth.signed_out"), "info")
    return redirect(url_for("main.index"))
