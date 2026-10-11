"""Guest IP: taken from the header Vercel controls, stored only as an HMAC fingerprint."""
import pytest

from app import create_app
from app.config import ProductionConfig
from app.services.client_ip import ip_fingerprint
from tests.fakes import FakeAIQuotaRepository, FakeCaptionsRepository


def test_fingerprint_is_stable_and_not_the_raw_ip(app):
    with app.app_context():
        first = ip_fingerprint("203.0.113.7")
        assert first == ip_fingerprint("203.0.113.7")
        assert "203.0.113.7" not in first
        assert first != ip_fingerprint("203.0.113.8")


def test_fingerprint_depends_on_the_secret_key(app):
    with app.app_context():
        first = ip_fingerprint("203.0.113.7")
        app.config["SECRET_KEY"] = "another-secret"
        assert ip_fingerprint("203.0.113.7") != first


def test_ipv6_addresses_in_one_64_block_count_as_one_guest(app):
    with app.app_context():
        assert ip_fingerprint("2001:db8:1:2::1") == ip_fingerprint("2001:db8:1:2:ffff::9")
        assert ip_fingerprint("2001:db8:1:2::1") != ip_fingerprint("2001:db8:1:3::1")


def test_ipv4_mapped_ipv6_counts_as_the_ipv4_address(app):
    with app.app_context():
        assert ip_fingerprint("::ffff:203.0.113.7") == ip_fingerprint("203.0.113.7")


@pytest.fixture
def production_client(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "prod-test-secret")
    app = create_app("production")
    app.extensions["captions_repository"] = FakeCaptionsRepository()
    repository = FakeAIQuotaRepository()
    app.extensions["ai_quota_repository"] = repository
    return app, app.test_client(), repository


def test_production_uses_the_ip_vercel_wrote_not_one_the_visitor_sent(production_client):
    app, client, repository = production_client
    # A visitor can put anything in X-Forwarded-For; Vercel's own entry is always the last one.
    with app.app_context():
        repository.consume_try(None, "captions", ip_fingerprint("198.51.100.4"), 3, 500)
    response = client.get("/api/captions/usage", headers={"X-Forwarded-For": "9.9.9.9, 198.51.100.4"})
    assert response.get_json()["used"] == 1
