"""Errors raised by the auth service. Each has a short `code`; messages.py turns it into friendly text."""


class AuthError(Exception):
    """Something the user can be told about, e.g. code="invalid_credentials"."""

    def __init__(self, code="unknown"):
        super().__init__(code)
        self.code = code


class AuthUnavailable(AuthError):
    """Supabase could not be reached or is not configured. Nothing is wrong with the user's account."""

    def __init__(self):
        super().__init__("unavailable")


class SessionEnded(AuthError):
    """The login in the cookie is no longer valid (logged out elsewhere, token revoked or broken)."""

    def __init__(self):
        super().__init__("session_ended")


class TokenExpired(AuthError):
    """The access token is too old; it can be renewed with the refresh token."""

    def __init__(self):
        super().__init__("token_expired")
