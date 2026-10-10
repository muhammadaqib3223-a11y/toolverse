"""Auth pages: signup, login, password reset, email links, Google login and logout.
Every page exists in English (/login) and Urdu (/ur/login)."""
import logging

from flask import flash, g, redirect, render_template, request, session, url_for
from flask_babel import gettext as _

from app.blueprints.auth import bp
from app.blueprints.auth.decorators import logged_out_only, login_optional
from app.blueprints.auth.errors import AuthError
from app.blueprints.auth.forms import (
    EmailLinkForm,
    ForgotPasswordForm,
    LoginForm,
    ResetPasswordForm,
    SignupForm,
)
from app.blueprints.auth.messages import error_message
from app.blueprints.auth.redirects import after_login_url, next_url_from_request, safe_next_url
from app.blueprints.auth.services import EMAIL_LINK_TYPES, get_auth_service
from app.blueprints.auth.session import current_auth_session, log_in, log_out
from app.i18n import localized_route

logger = logging.getLogger(__name__)

# Short-lived values kept in the session cookie between two requests.
CHECK_EMAIL_KEY = "check_email"            # which email we just sent, for /check-email
GOOGLE_VERIFIER_KEY = "google_code_verifier"  # PKCE secret, from /auth/google to /auth/callback
GOOGLE_NEXT_KEY = "google_next"            # page to open after Google login

RECOVERY = "recovery"


def _external_url(endpoint):
    """Full URL of one of our pages, in the current language (used in emails and by Google)."""
    return url_for(endpoint, _external=True)


def _show_check_email(kind, email):
    session[CHECK_EMAIL_KEY] = {"kind": kind, "email": email}
    return redirect(url_for("auth.check_email"))


@localized_route(bp, "/signup", methods=["GET", "POST"])
@logged_out_only
def signup():
    form = SignupForm()
    next_url = next_url_from_request()
    error = None
    if form.validate_on_submit():
        try:
            auth_session = get_auth_service().sign_up(
                form.email.data, form.password.data, confirm_url=_external_url("auth.email_link")
            )
        except AuthError as exc:
            error = error_message(exc)
        else:
            if auth_session is None:
                return _show_check_email("signup", form.email.data)
            # "Confirm email" is turned off in Supabase: the user is logged in right away.
            log_in(auth_session)
            flash(_("Welcome to Toolverse!"), "success")
            return redirect(after_login_url(next_url))
    return render_template("auth/signup.html", form=form, error=error, next_url=next_url)


@localized_route(bp, "/login", methods=["GET", "POST"])
@logged_out_only
def login():
    form = LoginForm()
    next_url = next_url_from_request()
    error = None
    if form.validate_on_submit():
        try:
            auth_session = get_auth_service().sign_in(form.email.data, form.password.data)
        except AuthError as exc:
            error = error_message(exc)
        else:
            log_in(auth_session)
            return redirect(after_login_url(next_url))
    return render_template("auth/login.html", form=form, error=error, next_url=next_url)


@localized_route(bp, "/forgot-password", methods=["GET", "POST"])
@logged_out_only
def forgot_password():
    form = ForgotPasswordForm()
    error = None
    if form.validate_on_submit():
        try:
            get_auth_service().send_password_reset(form.email.data, reset_url=_external_url("auth.email_link"))
        except AuthError as exc:
            # Only say so when it is about us, not about the email: the same message must show
            # whether or not the email has an account.
            if exc.code in ("rate_limited", "unavailable"):
                error = error_message(exc)
        if error is None:
            return _show_check_email("reset", form.email.data)
    return render_template("auth/forgot_password.html", form=form, error=error)


@localized_route(bp, "/check-email", methods=["GET"])
@login_optional
def check_email():
    sent = session.get(CHECK_EMAIL_KEY)
    if not isinstance(sent, dict):
        return redirect(url_for("auth.login"))
    return render_template("auth/check_email.html", kind=sent.get("kind"), email=sent.get("email", ""))


@localized_route(bp, "/auth/confirm", methods=["GET", "POST"])
@login_optional
def email_link():
    """Landing page of the links in our emails (confirm signup, reset password).

    The link carries a one-time token_hash, so it works on any device or browser. The token is
    only used when the user presses the button (POST), never on a plain page view.
    """
    form = EmailLinkForm()
    error = None
    if request.method == "GET":
        form.token_hash.data = request.args.get("token_hash", "")
        form.type.data = request.args.get("type", "")
        if not form.token_hash.data or form.type.data not in EMAIL_LINK_TYPES:
            error = error_message(AuthError("link_invalid"))
    elif form.validate_on_submit():
        try:
            auth_session = get_auth_service().verify_email_link(form.token_hash.data, form.type.data)
        except AuthError as exc:
            error = error_message(exc)
        else:
            log_in(auth_session)
            if form.type.data == RECOVERY:
                return redirect(url_for("auth.reset_password"))
            flash(_("Your email is confirmed. Welcome to Toolverse!"), "success")
            return redirect(url_for("dashboard.home"))
    else:
        error = error_message(AuthError("link_invalid"))
    return render_template("auth/email_link.html", form=form, is_recovery=form.type.data == RECOVERY, error=error)


@localized_route(bp, "/reset-password", methods=["GET", "POST"])
@login_optional
def reset_password():
    """Choose a new password. Reached from the reset email (which logs the user in first)."""
    auth_session = current_auth_session()
    if g.user is None or auth_session is None:
        flash(_("To choose a new password, open the reset link from your email."), "info")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    error = None
    if form.validate_on_submit():
        try:
            get_auth_service().update_password(auth_session, form.password.data)
        except AuthError as exc:
            error = error_message(exc)
        else:
            flash(_("Your password has been changed."), "success")
            return redirect(url_for("dashboard.home"))
    return render_template("auth/reset_password.html", form=form, error=error)


@localized_route(bp, "/auth/google", methods=["GET"])
@logged_out_only
def google_login():
    try:
        google = get_auth_service().start_google_login(_external_url("auth.google_callback"))
    except AuthError as exc:
        flash(str(error_message(exc)), "error")
        return redirect(url_for("auth.login"))
    session[GOOGLE_VERIFIER_KEY] = google.code_verifier
    session[GOOGLE_NEXT_KEY] = next_url_from_request()
    return redirect(google.url)


@localized_route(bp, "/auth/callback", methods=["GET"])
def google_callback():
    """Google sends the user back here (through Supabase) with a one-time code."""
    code_verifier = session.pop(GOOGLE_VERIFIER_KEY, None)
    next_url = safe_next_url(session.pop(GOOGLE_NEXT_KEY, None))

    if request.args.get("error"):
        # e.g. the user pressed "Cancel" on Google's page.
        logger.info("Google login returned an error: %s (%s)",
                    request.args.get("error"), request.args.get("error_description"))
        flash(str(error_message(AuthError("google_failed"))), "error")
        return redirect(url_for("auth.login"))

    code = request.args.get("code")
    if not code or not code_verifier:
        flash(str(error_message(AuthError("google_failed"))), "error")
        return redirect(url_for("auth.login"))

    try:
        auth_session = get_auth_service().finish_google_login(code, code_verifier)
    except AuthError as exc:
        flash(str(error_message(exc)), "error")
        return redirect(url_for("auth.login"))

    log_in(auth_session)
    return redirect(after_login_url(next_url))


@localized_route(bp, "/logout", methods=["POST"])
def logout():
    # POST only (with a CSRF token), so another site can't log people out with a link or image.
    auth_session = current_auth_session()
    if auth_session is not None:
        get_auth_service().sign_out(auth_session.access_token)
    log_out()
    flash(_("You're logged out. See you soon!"), "success")
    return redirect(url_for("marketing.index"))
