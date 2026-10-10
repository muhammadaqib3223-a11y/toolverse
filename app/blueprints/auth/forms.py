"""Auth forms: server-side validation + CSRF protection (Flask-WTF). Every message is translated."""
from flask import current_app
from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from wtforms import EmailField, HiddenField, PasswordField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class PasswordLength:
    """Password length rules from config (they must match the Supabase setting)."""

    def __call__(self, form, field):
        password = field.data or ""
        min_length = current_app.config["PASSWORD_MIN_LENGTH"]
        max_length = current_app.config["PASSWORD_MAX_LENGTH"]
        if len(password) < min_length:
            raise ValidationError(_("Use at least %(count)s characters.", count=min_length))
        if len(password.encode("utf-8")) > max_length:
            raise ValidationError(_("Use at most %(count)s characters.", count=max_length))


def _email_field():
    return EmailField(
        _l("Email"),
        filters=[_strip],
        validators=[
            DataRequired(message=_l("Please enter your email.")),
            Length(max=254, message=_l("Please enter a valid email address.")),
            Email(message=_l("Please enter a valid email address."), check_deliverability=False),
        ],
    )


class LoginForm(FlaskForm):
    email = _email_field()
    password = PasswordField(_l("Password"), validators=[DataRequired(message=_l("Please enter your password."))])


class SignupForm(FlaskForm):
    email = _email_field()
    password = PasswordField(
        _l("Password"),
        validators=[DataRequired(message=_l("Please choose a password.")), PasswordLength()],
    )


class ForgotPasswordForm(FlaskForm):
    email = _email_field()


class ResetPasswordForm(FlaskForm):
    password = PasswordField(
        _l("New password"),
        validators=[DataRequired(message=_l("Please choose a password.")), PasswordLength()],
    )
    confirm_password = PasswordField(
        _l("Repeat new password"),
        validators=[
            DataRequired(message=_l("Please type your new password again.")),
            EqualTo("password", message=_l("The two passwords don't match.")),
        ],
    )


class EmailLinkForm(FlaskForm):
    """The "Continue" button on /auth/confirm. The token is only used when the user clicks,
    so email scanners that open links automatically can't use it up."""
    token_hash = HiddenField(validators=[DataRequired()])
    type = HiddenField(validators=[DataRequired()])
