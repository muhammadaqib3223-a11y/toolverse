import pytest

from app import create_app
from app.blueprints.auth.session import SESSION_KEY
from tests.fakes import FakeAuthService


@pytest.fixture
def app():
    return create_app("testing")


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_service(app):
    """Replace Supabase with the fake auth service for this test."""
    service = FakeAuthService()
    app.extensions["auth_service"] = service
    return service


@pytest.fixture
def log_in(client, auth_service):
    """Log `client` in as a user (created if needed) without going through the login form."""
    def _log_in(email="sara@example.com", name="Sara Khan", expires_in=3600):
        if email not in auth_service.users:
            auth_service.add_user(email, name=name)
        auth_session = auth_service.new_session(email, expires_in=expires_in)
        with client.session_transaction() as session:
            session[SESSION_KEY] = {
                "access_token": auth_session.access_token,
                "refresh_token": auth_session.refresh_token,
                "expires_at": auth_session.expires_at,
            }
        return auth_session
    return _log_in
