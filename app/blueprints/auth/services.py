"""Everything that talks to Supabase Auth. Routes call these methods and never see Supabase errors:
every failure becomes an AuthError with a short code (see errors.py and messages.py).

The service is stored in app.extensions["auth_service"], so tests can swap in a fake one.
"""
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass

import httpx
import jwt
from flask import current_app
from supabase_auth.errors import (
    AuthApiError,
    AuthError as SupabaseAuthError,
    AuthRetryableError,
    AuthSessionMissingError,
)
from supabase_auth.helpers import generate_pkce_challenge, generate_pkce_verifier

from app.blueprints.auth import tokens
from app.blueprints.auth.errors import AuthError, AuthUnavailable, SessionEnded, TokenExpired
from app.services.supabase_client import SupabaseNotConfigured, create_supabase_client, supabase_url

logger = logging.getLogger(__name__)

# Supabase error code -> our error code (messages.py has the text for each).
_ERROR_CODES = {
    "invalid_credentials": "invalid_credentials",
    "email_not_confirmed": "email_not_confirmed",
    "weak_password": "weak_password",
    "same_password": "same_password",
    "email_address_invalid": "invalid_email",
    "validation_failed": "invalid_email",
    "email_address_not_authorized": "email_not_authorized",
    "signup_disabled": "signup_disabled",
    "email_provider_disabled": "signup_disabled",
    "over_email_send_rate_limit": "rate_limited",
    "over_request_rate_limit": "rate_limited",
    "otp_expired": "link_invalid",
    "bad_code_verifier": "google_failed",
    "flow_state_not_found": "google_failed",
    "flow_state_expired": "google_failed",
    "provider_disabled": "google_failed",
    "refresh_token_not_found": "session_ended",
    "refresh_token_already_used": "session_ended",
    "session_not_found": "session_ended",
    "session_expired": "session_ended",
    "user_not_found": "session_ended",
    "bad_jwt": "session_ended",
    "invalid_jwt": "session_ended",
    "user_already_exists": "already_registered",
    "email_exists": "already_registered",
}

# Email link types we accept on /auth/confirm (they come from our Supabase email templates).
EMAIL_LINK_TYPES = frozenset({"email", "signup", "recovery"})


@dataclass(frozen=True)
class AuthSession:
    """A login: the tokens we keep in the user's cookie."""
    access_token: str
    refresh_token: str
    expires_at: int  # unix time when the access token expires


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str
    name: str = ""

    @property
    def display_name(self):
        return self.name or self.email.split("@", 1)[0]


@dataclass(frozen=True)
class GoogleLogin:
    """Where to send the user, and the secret (PKCE verifier) to keep until they come back."""
    url: str
    code_verifier: str


def get_auth_service():
    return current_app.extensions["auth_service"]


class SupabaseAuthService:
    def sign_up(self, email, password, confirm_url):
        """Create an account. Returns an AuthSession if the user is logged in straight away,
        or None if they must confirm their email first.

        "Email already registered" also returns None, so nobody can find out which emails have accounts.
        """
        try:
            with self._errors("sign_up"):
                response = self._client().auth.sign_up({
                    "email": email,
                    "password": password,
                    "options": {"email_redirect_to": confirm_url},
                })
        except AuthError as error:
            if error.code == "already_registered":
                return None
            raise
        return _to_session(response.session) if response.session else None

    def sign_in(self, email, password):
        with self._errors("sign_in"):
            response = self._client().auth.sign_in_with_password({"email": email, "password": password})
        return _to_session(response.session)

    def send_password_reset(self, email, reset_url):
        with self._errors("send_password_reset"):
            self._client().auth.reset_password_for_email(email, {"redirect_to": reset_url})

    def verify_email_link(self, token_hash, link_type):
        """Check the token from an email link (signup confirmation or password reset) and log in."""
        if link_type not in EMAIL_LINK_TYPES or not token_hash:
            raise AuthError("link_invalid")
        with self._errors("verify_email_link"):
            response = self._client().auth.verify_otp({"token_hash": token_hash, "type": link_type})
        if not response.session:
            raise AuthError("link_invalid")
        return _to_session(response.session)

    def update_password(self, auth_session, new_password):
        with self._errors("update_password"):
            client = self._client()
            client.auth.set_session(auth_session.access_token, auth_session.refresh_token)
            client.auth.update_user({"password": new_password})

    def start_google_login(self, callback_url):
        """Build the Google login URL (PKCE). No network call is made here."""
        code_verifier = generate_pkce_verifier()
        with self._errors("start_google_login"):
            response = self._client().auth.sign_in_with_oauth({
                "provider": "google",
                "options": {
                    "redirect_to": callback_url,
                    "query_params": {
                        "code_challenge": generate_pkce_challenge(code_verifier),
                        "code_challenge_method": "s256",
                    },
                },
            })
        return GoogleLogin(url=response.url, code_verifier=code_verifier)

    def finish_google_login(self, code, code_verifier):
        with self._errors("finish_google_login"):
            response = self._client().auth.exchange_code_for_session(
                {"auth_code": code, "code_verifier": code_verifier}
            )
        return _to_session(response.session)

    def refresh(self, refresh_token):
        with self._errors("refresh"):
            response = self._client().auth.refresh_session(refresh_token)
        return _to_session(response.session)

    def sign_out(self, access_token):
        """End this login on Supabase too. Best effort: the cookie is cleared either way."""
        try:
            with self._errors("sign_out"):
                self._client().auth.admin.sign_out(access_token, "local")
        except AuthError:
            pass

    def get_user(self, access_token):
        """The user an access token belongs to. Raises TokenExpired, SessionEnded or AuthUnavailable."""
        config = current_app.config
        try:
            claims = tokens.read_claims(
                access_token,
                supabase_url(),
                config["SUPABASE_PUBLISHABLE_KEY"],
                config["SUPABASE_TIMEOUT_SECONDS"],
            )
        except jwt.ExpiredSignatureError:
            raise TokenExpired() from None
        except jwt.PyJWKClientConnectionError:
            logger.warning("Could not download Supabase signing keys", exc_info=True)
            raise AuthUnavailable() from None
        except tokens.LegacySecretToken:
            return self._get_user_from_supabase(access_token)
        except jwt.PyJWTError as error:  # bad signature, wrong audience, unknown key, broken token...
            logger.info("Rejected access token: %s", error)
            raise SessionEnded() from None
        return _user_from_claims(claims)

    def _get_user_from_supabase(self, access_token):
        try:
            claims = jwt.decode(access_token, options={"verify_signature": False})
        except jwt.PyJWTError:
            raise SessionEnded() from None
        if claims.get("exp", 0) <= time.time():
            raise TokenExpired()
        with self._errors("get_user"):
            response = self._client().auth.get_user(access_token)
        if response is None or response.user is None:
            raise SessionEnded()
        user = response.user
        return AuthUser(id=user.id, email=user.email or "", name=_name_from_metadata(user.user_metadata))

    def _client(self):
        return create_supabase_client()

    @contextmanager
    def _errors(self, action):
        """Turn Supabase/network errors into AuthError, and log the details for the developer."""
        try:
            yield
        except AuthError:
            raise
        except SupabaseNotConfigured:
            logger.error("Supabase is not configured: set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY")
            raise AuthUnavailable() from None
        except (AuthRetryableError, httpx.HTTPError) as error:
            logger.warning("Supabase unreachable during %s: %s", action, error)
            raise AuthUnavailable() from None
        except AuthApiError as error:
            code = _ERROR_CODES.get(error.code or "", "unknown")
            log = logger.warning if code == "unknown" else logger.info
            log("Supabase auth error during %s: status=%s code=%s message=%s",
                action, error.status, error.code, error.message)
            if code == "session_ended":
                raise SessionEnded() from None
            raise AuthError(code) from None
        except AuthSessionMissingError:
            raise SessionEnded() from None
        except SupabaseAuthError as error:
            code = _ERROR_CODES.get(getattr(error, "code", None) or "", "unknown")
            logger.warning("Supabase auth error during %s: %s (%s)", action, error, type(error).__name__)
            raise AuthError(code) from None


def _to_session(session):
    expires_at = session.expires_at or int(time.time()) + (session.expires_in or 0)
    return AuthSession(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_at=int(expires_at),
    )


def _user_from_claims(claims):
    return AuthUser(
        id=claims["sub"],
        email=claims.get("email") or "",
        name=_name_from_metadata(claims.get("user_metadata")),
    )


def _name_from_metadata(metadata):
    # Google fills these in; email sign-ups have no name.
    metadata = metadata or {}
    name = metadata.get("full_name") or metadata.get("name") or ""
    return name.strip() if isinstance(name, str) else ""
