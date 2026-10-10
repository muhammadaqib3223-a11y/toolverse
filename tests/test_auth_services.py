"""SupabaseAuthService: Supabase errors become friendly codes, and tokens are checked locally.
No network: the Supabase client and the public signing keys are faked."""
import time
from types import SimpleNamespace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from supabase_auth.errors import AuthApiError, AuthRetryableError, AuthWeakPasswordError
from supabase_auth.helpers import generate_pkce_challenge

from app.blueprints.auth import tokens
from app.blueprints.auth.errors import AuthError, AuthUnavailable, SessionEnded, TokenExpired
from app.blueprints.auth.services import SupabaseAuthService

SUPABASE_URL = "https://test-project.supabase.co"  # TestingConfig.SUPABASE_URL
KEY_ID = "test-key-1"


@pytest.fixture
def ctx(app):
    with app.test_request_context():
        yield


def _service_with_client(monkeypatch, **auth_methods):
    service = SupabaseAuthService()
    fake_client = SimpleNamespace(auth=SimpleNamespace(**auth_methods))
    monkeypatch.setattr(service, "_client", lambda: fake_client)
    return service


def _raises(error):
    def method(*args, **kwargs):
        raise error
    return method


# --- Error mapping ---

@pytest.mark.parametrize("supabase_error,code", [
    (AuthApiError("Invalid login credentials", 400, "invalid_credentials"), "invalid_credentials"),
    (AuthApiError("Email not confirmed", 400, "email_not_confirmed"), "email_not_confirmed"),
    (AuthApiError("Too many", 429, "over_request_rate_limit"), "rate_limited"),
    (AuthApiError("Strange", 400, "something_new"), "unknown"),
    (AuthWeakPasswordError("Weak", 422, ["pwned"]), "weak_password"),
])
def test_supabase_errors_become_friendly_codes(ctx, monkeypatch, supabase_error, code):
    service = _service_with_client(monkeypatch, sign_in_with_password=_raises(supabase_error))
    with pytest.raises(AuthError) as caught:
        service.sign_in("sara@example.com", "pw")
    assert caught.value.code == code


@pytest.mark.parametrize("network_error", [
    httpx.ConnectError("no route"),
    httpx.ReadTimeout("slow"),
    AuthRetryableError("bad gateway", 502),
])
def test_network_problems_mean_unavailable(ctx, monkeypatch, network_error):
    service = _service_with_client(monkeypatch, sign_in_with_password=_raises(network_error))
    with pytest.raises(AuthUnavailable):
        service.sign_in("sara@example.com", "pw")


def test_missing_settings_mean_unavailable(app, monkeypatch):
    app.config["SUPABASE_URL"] = ""
    with app.test_request_context(), pytest.raises(AuthUnavailable):
        SupabaseAuthService().sign_in("sara@example.com", "pw")


def test_sign_up_with_a_taken_email_returns_none(ctx, monkeypatch):
    service = _service_with_client(
        monkeypatch, sign_up=_raises(AuthApiError("exists", 422, "user_already_exists")))
    assert service.sign_up("taken@example.com", "long-enough-1", "http://localhost/auth/confirm") is None


def test_sign_up_waiting_for_email_confirmation_returns_none(ctx, monkeypatch):
    service = _service_with_client(monkeypatch, sign_up=lambda credentials: SimpleNamespace(session=None))
    assert service.sign_up("new@example.com", "long-enough-1", "http://localhost/auth/confirm") is None


def test_unknown_email_link_type_is_rejected_without_calling_supabase(ctx, monkeypatch):
    service = _service_with_client(monkeypatch, verify_otp=_raises(AssertionError("must not be called")))
    with pytest.raises(AuthError) as caught:
        service.verify_email_link("abc", "magiclink")
    assert caught.value.code == "link_invalid"


def test_sign_out_never_fails(ctx, monkeypatch):
    service = _service_with_client(
        monkeypatch, admin=SimpleNamespace(sign_out=_raises(httpx.ConnectError("down"))))
    service.sign_out("token")  # no exception


def test_google_login_url_uses_pkce(ctx):
    google = SupabaseAuthService().start_google_login("http://localhost/auth/callback")
    query = httpx.URL(google.url).params
    assert google.url.startswith(f"{SUPABASE_URL}/auth/v1/authorize?")
    assert query["provider"] == "google"
    assert query["redirect_to"] == "http://localhost/auth/callback"
    assert query["code_challenge"] == generate_pkce_challenge(google.code_verifier)
    assert query["code_challenge_method"] == "s256"
    assert google.code_verifier not in google.url


# --- Checking access tokens locally ---

@pytest.fixture
def signing_key(monkeypatch):
    """A private key, with its public half served as the project's JWKS (no download)."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_jwk = jwt.algorithms.ECAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    public_jwk.update(kid=KEY_ID, alg="ES256", use="sig")

    client = jwt.PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
    monkeypatch.setattr(client, "fetch_data", lambda: {"keys": [public_jwk]})
    monkeypatch.setitem(tokens._jwks_clients, SUPABASE_URL, client)
    return private_key


def _token(private_key, kid=KEY_ID, **overrides):
    claims = {
        "sub": "user-123",
        "email": "sara@example.com",
        "aud": "authenticated",
        "iss": f"{SUPABASE_URL}/auth/v1",
        "exp": int(time.time()) + 3600,
        "user_metadata": {"full_name": "Sara Khan"},
        **overrides,
    }
    return jwt.encode(claims, private_key, algorithm="ES256", headers={"kid": kid})


def test_valid_token_gives_the_user(ctx, signing_key):
    user = SupabaseAuthService().get_user(_token(signing_key))
    assert (user.id, user.email, user.name, user.display_name) == ("user-123", "sara@example.com", "Sara Khan", "Sara Khan")


def test_expired_token(ctx, signing_key):
    with pytest.raises(TokenExpired):
        SupabaseAuthService().get_user(_token(signing_key, exp=int(time.time()) - 60))


@pytest.mark.parametrize("overrides", [
    {"aud": "anon"},
    {"iss": "https://other-project.supabase.co/auth/v1"},
])
def test_token_for_someone_else_is_rejected(ctx, signing_key, overrides):
    with pytest.raises(SessionEnded):
        SupabaseAuthService().get_user(_token(signing_key, **overrides))


def test_forged_token_is_rejected(ctx, signing_key):
    forger_key = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(SessionEnded):
        SupabaseAuthService().get_user(_token(forger_key))


def test_unknown_signing_key_is_rejected(ctx, signing_key):
    with pytest.raises(SessionEnded):
        SupabaseAuthService().get_user(_token(signing_key, kid="unknown-key"))


@pytest.mark.parametrize("token", ["not-a-jwt", "a.b.c", ""])
def test_garbage_token_is_rejected(ctx, signing_key, token):
    with pytest.raises(SessionEnded):
        SupabaseAuthService().get_user(token)


def test_unsigned_token_is_rejected(ctx, signing_key):
    token = jwt.encode({"sub": "user-123", "exp": int(time.time()) + 60}, None, algorithm="none")
    with pytest.raises(SessionEnded):
        SupabaseAuthService().get_user(token)


def test_jwks_download_failure_means_unavailable(ctx, monkeypatch, signing_key):
    token = _token(signing_key)
    client = jwt.PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
    monkeypatch.setattr(client, "fetch_data", _raises(jwt.PyJWKClientConnectionError("down")))
    monkeypatch.setitem(tokens._jwks_clients, SUPABASE_URL, client)
    with pytest.raises(AuthUnavailable):
        SupabaseAuthService().get_user(token)


def test_legacy_hs256_tokens_are_checked_by_supabase(ctx, monkeypatch):
    token = jwt.encode({"sub": "user-9", "exp": int(time.time()) + 60}, "project-secret-that-we-do-not-know-1234",
                       algorithm="HS256")
    supabase_user = SimpleNamespace(id="user-9", email="old@example.com", user_metadata={"name": "Old Project"})
    service = _service_with_client(monkeypatch, get_user=lambda jwt_: SimpleNamespace(user=supabase_user))
    user = service.get_user(token)
    assert (user.id, user.email, user.name) == ("user-9", "old@example.com", "Old Project")


def test_legacy_hs256_token_rejected_by_supabase(ctx, monkeypatch):
    token = jwt.encode({"sub": "user-9", "exp": int(time.time()) + 60}, "secret-of-at-least-32-bytes-long!",
                       algorithm="HS256")
    service = _service_with_client(
        monkeypatch, get_user=_raises(AuthApiError("invalid JWT", 403, "bad_jwt")))
    with pytest.raises(SessionEnded):
        service.get_user(token)
