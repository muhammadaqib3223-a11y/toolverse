"""The login cookie, and who the current user is (g.user).

Flask's session is a signed cookie (HttpOnly, SameSite=Lax, Secure in production). We keep only
the two Supabase tokens and their expiry time in it, never the whole user object, so the
cookie stays well under the browser's 4 KB limit.
"""
import logging
import time

from flask import g, session

from app.blueprints.auth.errors import AuthError, AuthUnavailable, SessionEnded, TokenExpired
from app.blueprints.auth.services import AuthSession, get_auth_service

logger = logging.getLogger(__name__)

SESSION_KEY = "auth"
# Renew the access token a little before it expires, so it never runs out in the middle of a request.
REFRESH_MARGIN_SECONDS = 60


def log_in(auth_session):
    """Remember a new login. Any old session data (half-finished Google login etc.) is dropped."""
    session.clear()
    _store(auth_session)
    session.permanent = True


def log_out():
    session.clear()
    g.user = None


def current_auth_session():
    """The tokens of the logged-in user, or None."""
    data = session.get(SESSION_KEY)
    if not isinstance(data, dict):
        return None
    try:
        return AuthSession(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=int(data["expires_at"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def load_current_user():
    """Runs before every request: sets g.user to the logged-in AuthUser, or None."""
    g.user = None
    auth_session = current_auth_session()
    if auth_session is None:
        if SESSION_KEY in session:  # broken cookie data
            session.pop(SESSION_KEY)
        return

    service = get_auth_service()
    try:
        if auth_session.expires_at - time.time() < REFRESH_MARGIN_SECONDS:
            auth_session = _refresh(service, auth_session)
        try:
            g.user = service.get_user(auth_session.access_token)
        except TokenExpired:
            auth_session = _refresh(service, auth_session)
            g.user = service.get_user(auth_session.access_token)
    except (SessionEnded, TokenExpired):
        # The login is over (logged out elsewhere, password changed, token revoked...).
        session.pop(SESSION_KEY, None)
    except AuthUnavailable:
        # Supabase could not be reached. Keep the cookie: the user is still logged in, we just
        # can't confirm it on this request.
        logger.warning("Could not check the login on this request; keeping the session")
    except Exception:
        logger.exception("Unexpected error while checking the login")


def _refresh(service, auth_session):
    try:
        new_session = service.refresh(auth_session.refresh_token)
    except AuthUnavailable:
        raise
    except AuthError as error:
        if error.code == "rate_limited":  # try again on a later request
            raise AuthUnavailable() from None
        raise SessionEnded() from None
    _store(new_session)
    return new_session


def _store(auth_session):
    session[SESSION_KEY] = {
        "access_token": auth_session.access_token,
        "refresh_token": auth_session.refresh_token,
        "expires_at": auth_session.expires_at,
    }
