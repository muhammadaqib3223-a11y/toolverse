"""Auth pages and the login cookie, with the fake auth service (no network)."""
import html as html_lib
import re
import secrets
import time

import pytest

from app.blueprints.auth.errors import AuthError
from app.blueprints.auth.redirects import safe_next_url
from app.blueprints.auth.routes import CHECK_EMAIL_KEY, GOOGLE_NEXT_KEY, GOOGLE_VERIFIER_KEY
from app.blueprints.auth.services import AuthSession
from app.blueprints.auth.session import SESSION_KEY
from tests.fakes import GOOGLE_CODE, GOOGLE_URL, GOOGLE_VERIFIER


def _html(response):
    """The page with HTML entities decoded (' -> '), so tests can compare plain text."""
    return html_lib.unescape(response.get_data(as_text=True))


def _session(client):
    with client.session_transaction() as session:
        return dict(session)


# --- Pages render ---

@pytest.mark.parametrize("path", ["/login", "/signup", "/forgot-password", "/ur/login", "/ur/signup"])
def test_auth_pages_render(client, auth_service, path):
    response = client.get(path)
    assert response.status_code == 200
    assert 'type="email"' in _html(response)
    assert response.headers["Cache-Control"] == "private, no-store"


def test_login_and_signup_offer_google(client, auth_service):
    for path in ["/login", "/signup"]:
        assert 'href="/auth/google"' in _html(client.get(path))


def test_urdu_login_page_is_rtl_and_translated(client, auth_service):
    html = _html(client.get("/ur/login"))
    assert 'lang="ur" dir="rtl"' in html
    assert "گوگل کے ساتھ جاری رکھیں" in html  # "Continue with Google"
    assert 'href="/ur/auth/google"' in html
    assert 'href="/ur/forgot-password"' in html


def test_utility_pages_are_noindex_but_login_is_not(client, auth_service):
    assert 'name="robots" content="noindex"' in _html(client.get("/forgot-password"))
    assert 'name="robots"' not in _html(client.get("/login"))


# --- Signup ---

def test_signup_sends_a_confirmation_email(client, auth_service):
    response = client.post("/signup", data={"email": " new@example.com ", "password": "long-enough-1"})
    assert response.status_code == 302
    assert response.headers["Location"] == "/check-email"

    (email, password, confirm_url), = auth_service.called("sign_up")
    assert email == "new@example.com"  # spaces trimmed
    assert confirm_url == "http://localhost/auth/confirm"

    html = _html(client.get("/check-email"))
    assert "Check your email." in html
    assert "new@example.com" in html
    assert SESSION_KEY not in _session(client)


def test_urdu_signup_email_link_opens_in_urdu(client, auth_service):
    client.post("/ur/signup", data={"email": "new@example.com", "password": "long-enough-1"})
    (_, _, confirm_url), = auth_service.called("sign_up")
    assert confirm_url == "http://localhost/ur/auth/confirm"


def test_signup_with_an_existing_email_looks_the_same(client, auth_service):
    auth_service.add_user("taken@example.com")
    response = client.post("/signup", data={"email": "taken@example.com", "password": "long-enough-1"})
    assert response.headers["Location"] == "/check-email"


def test_signup_logs_in_directly_when_email_confirmation_is_off(client, auth_service):
    auth_service.confirm_email = False
    response = client.post("/signup", data={"email": "new@example.com", "password": "long-enough-1"})
    assert response.headers["Location"] == "/dashboard"
    assert SESSION_KEY in _session(client)


@pytest.mark.parametrize("data,message", [
    ({"email": "new@example.com", "password": "short"}, "Use at least 8 characters."),
    ({"email": "not-an-email", "password": "long-enough-1"}, "Please enter a valid email address."),
    ({"email": "", "password": "long-enough-1"}, "Please enter your email."),
    ({"email": "new@example.com", "password": "x" * 73}, "Use at most 72 characters."),
])
def test_signup_validates_on_the_server(client, auth_service, data, message):
    response = client.post("/signup", data=data)
    assert response.status_code == 200
    assert message in _html(response)
    assert 'aria-invalid="true"' in _html(response)
    assert auth_service.called("sign_up") == []


def test_signup_shows_friendly_supabase_errors(client, auth_service):
    auth_service.fail_next = AuthError("weak_password")
    html = _html(client.post("/signup", data={"email": "new@example.com", "password": "password123"}))
    assert "This password is too weak or too common." in html
    assert 'role="alert"' in html


# --- Login ---

def test_login_goes_to_the_dashboard(client, auth_service):
    auth_service.add_user("sara@example.com", "correct-horse", name="Sara Khan")
    response = client.post("/login", data={"email": "sara@example.com", "password": "correct-horse"})
    assert response.headers["Location"] == "/dashboard"

    stored = _session(client)[SESSION_KEY]
    assert set(stored) == {"access_token", "refresh_token", "expires_at"}
    assert "Sara Khan" in _html(client.get("/dashboard"))


def test_login_with_a_wrong_password(client, auth_service):
    auth_service.add_user("sara@example.com", "correct-horse")
    response = client.post("/login", data={"email": "sara@example.com", "password": "wrong-horse"})
    assert response.status_code == 200
    assert "That email and password don't match." in _html(response)
    assert SESSION_KEY not in _session(client)


def test_login_before_confirming_the_email(client, auth_service):
    auth_service.add_user("sara@example.com", "correct-horse", confirmed=False)
    html = _html(client.post("/login", data={"email": "sara@example.com", "password": "correct-horse"}))
    assert "Please confirm your email first." in html


def test_login_when_supabase_is_down(client, auth_service):
    auth_service.unavailable = True
    html = _html(client.post("/login", data={"email": "sara@example.com", "password": "correct-horse"}))
    assert "Login isn't available right now." in html


def test_login_returns_to_the_page_the_user_wanted(client, auth_service):
    auth_service.add_user("sara@example.com", "correct-horse")
    response = client.post("/login?next=/ur/dashboard%3Ftab%3D1",
                           data={"email": "sara@example.com", "password": "correct-horse"})
    assert response.headers["Location"] == "/ur/dashboard?tab=1"


@pytest.mark.parametrize("next_url", ["https://evil.example", "//evil.example", "/\\evil.example", "javascript:alert(1)"])
def test_login_never_redirects_to_another_site(client, auth_service, next_url):
    auth_service.add_user("sara@example.com", "correct-horse")
    response = client.post("/login", query_string={"next": next_url},
                           data={"email": "sara@example.com", "password": "correct-horse"})
    assert response.headers["Location"] == "/dashboard"


@pytest.mark.parametrize("target,expected", [
    ("/dashboard", "/dashboard"),
    ("/ur/tools/notes?x=1", "/ur/tools/notes?x=1"),
    ("https://evil.example/", None),
    ("//evil.example", None),
    ("/\\evil.example", None),
    ("/ok\r\nSet-Cookie: x", None),
    ("dashboard", None),
    ("", None),
    (None, None),
])
def test_safe_next_url(target, expected):
    assert safe_next_url(target) == expected


def test_logged_in_users_skip_the_login_page(client, log_in):
    log_in()
    assert client.get("/login").headers["Location"] == "/dashboard"
    assert client.get("/ur/signup").headers["Location"] == "/ur/dashboard"


# --- Logout ---

def test_logout(client, auth_service, log_in):
    auth_session = log_in()
    response = client.post("/logout")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert SESSION_KEY not in _session(client)
    assert auth_service.called("sign_out") == [(auth_session.access_token,)]

    html = _html(client.get("/"))
    assert "You're logged out." in html
    assert 'href="/login"' in html


def test_logout_in_urdu_returns_to_the_urdu_home_page(client, log_in):
    log_in()
    assert client.post("/ur/logout").headers["Location"] == "/ur"


def test_logout_needs_post(client, log_in):
    log_in()
    assert client.get("/logout").status_code == 405


def test_forms_need_a_csrf_token(app, client, log_in):
    log_in()
    app.config["WTF_CSRF_ENABLED"] = True
    response = client.post("/logout")
    assert response.status_code == 302
    assert SESSION_KEY in _session(client)  # not logged out
    assert "This form expired." in _html(client.get("/"))


def test_logout_form_carries_a_csrf_token(app, client, log_in):
    log_in()
    app.config["WTF_CSRF_ENABLED"] = True
    html = _html(client.get("/dashboard"))
    token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
    assert client.post("/logout", data={"csrf_token": token}).headers["Location"] == "/"
    assert SESSION_KEY not in _session(client)


# --- Navbar ---

def test_navbar_for_guests_and_for_logged_in_users(client, log_in):
    html = _html(client.get("/"))
    assert 'href="/login"' in html and 'href="/signup"' in html

    log_in()
    html = _html(client.get("/"))
    assert 'href="/dashboard"' in html
    assert 'action="/logout"' in html
    assert 'href="/login"' not in html


# --- Forgot / reset password ---

def test_forgot_password_always_shows_the_same_message(client, auth_service):
    auth_service.add_user("sara@example.com")
    for email in ["sara@example.com", "nobody@example.com"]:
        response = client.post("/forgot-password", data={"email": email})
        assert response.headers["Location"] == "/check-email"
        assert "If an account exists for <strong" in _html(client.get("/check-email"))

    (_, reset_url), _ = auth_service.called("send_password_reset")
    assert reset_url == "http://localhost/auth/confirm"


def test_forgot_password_hides_email_specific_errors(client, auth_service):
    auth_service.fail_next = AuthError("email_not_authorized")
    response = client.post("/forgot-password", data={"email": "nobody@example.com"})
    assert response.headers["Location"] == "/check-email"


def test_forgot_password_rate_limit_is_shown(client, auth_service):
    auth_service.fail_next = AuthError("rate_limited")
    html = _html(client.post("/forgot-password", data={"email": "sara@example.com"}))
    assert "Too many attempts." in html


def test_check_email_without_a_sent_email_goes_to_login(client, auth_service):
    assert client.get("/check-email").headers["Location"] == "/login"


def test_reset_password_needs_the_email_link(client, auth_service):
    response = client.get("/reset-password")
    assert response.headers["Location"] == "/forgot-password"


def test_reset_password(client, auth_service, log_in):
    auth_session = log_in()
    data = {"password": "brand-new-pass", "confirm_password": "brand-new-pass"}
    response = client.post("/reset-password", data=data)
    assert response.headers["Location"] == "/dashboard"
    assert auth_service.called("update_password") == [(auth_session.access_token, "brand-new-pass")]
    assert "Your password has been changed." in _html(client.get("/dashboard"))


def test_reset_password_must_match(client, auth_service, log_in):
    log_in()
    html = _html(client.post("/reset-password", data={"password": "brand-new-pass", "confirm_password": "other"}))
    assert "The two passwords don't match." in html
    assert auth_service.called("update_password") == []


# --- Email links (/auth/confirm) ---

def test_opening_an_email_link_does_not_use_the_token(client, auth_service):
    auth_service.add_user("new@example.com", confirmed=False)
    html = _html(client.get("/auth/confirm?token_hash=good-token-for-new@example.com&type=email"))
    assert "Confirm my email" in html
    assert 'value="good-token-for-new@example.com"' in html
    assert auth_service.called("verify_email_link") == []


def test_confirming_the_email_logs_in(client, auth_service):
    auth_service.add_user("new@example.com", confirmed=False)
    response = client.post("/auth/confirm", data={"token_hash": "good-token-for-new@example.com", "type": "email"})
    assert response.headers["Location"] == "/dashboard"
    assert "Your email is confirmed." in _html(client.get("/dashboard"))


def test_password_reset_link_leads_to_the_new_password_form(client, auth_service):
    auth_service.add_user("sara@example.com")
    response = client.post("/ur/auth/confirm", data={"token_hash": "good-token-for-sara@example.com", "type": "recovery"})
    assert response.headers["Location"] == "/ur/reset-password"
    assert client.get("/ur/reset-password").status_code == 200


@pytest.mark.parametrize("query", ["", "?token_hash=abc", "?token_hash=abc&type=magic", "?type=email"])
def test_broken_email_links(client, auth_service, query):
    html = _html(client.get(f"/auth/confirm{query}"))
    assert "This link doesn't work." in html
    assert "Confirm my email" not in html


def test_expired_email_link(client, auth_service):
    response = client.post("/auth/confirm", data={"token_hash": "used-token", "type": "email"})
    assert "This link has expired or was already used." in _html(response)
    assert SESSION_KEY not in _session(client)


# --- Google login ---

def test_google_login_starts_with_pkce(client, auth_service):
    response = client.get("/auth/google?next=/dashboard")
    assert response.status_code == 302
    assert response.headers["Location"].startswith(GOOGLE_URL)
    (callback_url,), = auth_service.called("start_google_login")
    assert callback_url == "http://localhost/auth/callback"

    session = _session(client)
    assert session[GOOGLE_VERIFIER_KEY] == GOOGLE_VERIFIER
    assert session[GOOGLE_NEXT_KEY] == "/dashboard"


def test_google_login_in_urdu_comes_back_to_urdu(client, auth_service):
    client.get("/ur/auth/google")
    (callback_url,), = auth_service.called("start_google_login")
    assert callback_url == "http://localhost/ur/auth/callback"


def test_google_callback_logs_in(client, auth_service):
    client.get("/auth/google?next=/tools")
    response = client.get(f"/auth/callback?code={GOOGLE_CODE}")
    assert response.headers["Location"] == "/tools"
    session = _session(client)
    assert SESSION_KEY in session and GOOGLE_VERIFIER_KEY not in session
    assert "Google User" in _html(client.get("/dashboard"))


def test_google_callback_without_starting_login_fails_safely(client, auth_service):
    response = client.get(f"/auth/callback?code={GOOGLE_CODE}")
    assert response.headers["Location"] == "/login"
    assert auth_service.called("finish_google_login") == []
    assert "Google login didn't work." in _html(client.get("/login"))


def test_google_cancelled(client, auth_service):
    client.get("/auth/google")
    response = client.get("/auth/callback?error=access_denied&error_description=cancelled")
    assert response.headers["Location"] == "/login"
    assert SESSION_KEY not in _session(client)


def test_google_login_when_supabase_is_down(client, auth_service):
    auth_service.unavailable = True
    assert client.get("/auth/google").headers["Location"] == "/login"
    assert "Login isn't available right now." in _html(client.get("/login"))


# --- The login cookie ---

def test_expiring_token_is_refreshed(client, auth_service, log_in):
    old = log_in(expires_in=30)  # inside the refresh margin
    assert client.get("/dashboard").status_code == 200
    stored = _session(client)[SESSION_KEY]
    assert stored["access_token"] != old.access_token
    assert stored["expires_at"] > time.time() + 3000
    assert auth_service.called("refresh") == [(old.refresh_token,)]


def test_token_rejected_as_expired_is_refreshed(client, auth_service, log_in):
    old = log_in()
    auth_service.expired_tokens.add(old.access_token)
    assert client.get("/dashboard").status_code == 200
    assert _session(client)[SESSION_KEY]["access_token"] != old.access_token


def test_failed_refresh_logs_out(client, auth_service, log_in):
    old = log_in(expires_in=30)
    auth_service.refresh_tokens.pop(old.refresh_token)  # revoked
    assert client.get("/dashboard").headers["Location"].startswith("/login")
    assert SESSION_KEY not in _session(client)


def test_revoked_token_logs_out(client, auth_service, log_in):
    old = log_in()
    auth_service.access_tokens.pop(old.access_token)
    client.get("/")
    assert SESSION_KEY not in _session(client)


def test_supabase_down_keeps_the_cookie(client, auth_service, log_in):
    log_in()
    auth_service.unavailable = True
    assert client.get("/dashboard").headers["Location"].startswith("/login")
    assert SESSION_KEY in _session(client)


def test_broken_cookie_data_is_dropped(client, auth_service):
    with client.session_transaction() as session:
        session[SESSION_KEY] = {"access_token": "x"}
    assert client.get("/").status_code == 200
    assert SESSION_KEY not in _session(client)


def test_login_cookie_stays_small(app, client, auth_service):
    # Real Supabase tokens are ~1–1.5 KB (more for Google users); the cookie must stay under 4 KB.
    auth_service.add_user("sara@example.com", "correct-horse")
    auth_service.new_session = lambda email, expires_in=3600: _big_session(auth_service, email)
    response = client.post("/login", data={"email": "sara@example.com", "password": "correct-horse"})
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert len(cookie) < 4000


def _big_session(service, email):
    access = secrets.token_urlsafe(1500)[:2000]
    service.access_tokens[access] = email
    return AuthSession(access_token=access, refresh_token=secrets.token_urlsafe(16), expires_at=int(time.time()) + 3600)


def test_production_login_cookie_is_secure():
    from app import config
    assert config.ProductionConfig.SESSION_COOKIE_SECURE is True
