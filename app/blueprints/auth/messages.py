"""Friendly, translated text for each auth error code (see errors.py and services.py)."""
from flask_babel import lazy_gettext as _l

ERROR_MESSAGES = {
    "invalid_credentials": _l("That email and password don't match. Please try again."),
    "email_not_confirmed": _l("Please confirm your email first. Open the link we sent you."),
    "weak_password": _l("This password is too weak or too common. Please choose a stronger one."),
    "same_password": _l("Your new password must be different from the old one."),
    "invalid_email": _l("Please enter a valid email address."),
    "email_not_authorized": _l("We can't send emails to this address yet. Please try another email."),
    "signup_disabled": _l("New sign-ups are paused right now. Please try again later."),
    "rate_limited": _l("Too many attempts. Please wait a few minutes and try again."),
    "link_invalid": _l("This link has expired or was already used. Please ask for a new one."),
    "google_failed": _l("Google login didn't work. Please try again."),
    "session_ended": _l("Your session has ended. Please log in again."),
    "unavailable": _l("Login isn't available right now. Please try again in a few minutes."),
    "unknown": _l("Something went wrong. Please try again."),
}


def error_message(error):
    """Text to show the user for an AuthError."""
    return ERROR_MESSAGES.get(error.code, ERROR_MESSAGES["unknown"])
