"""HTTP routes and rules for the Caption Generator. Uses fake Supabase + fake AI only."""
import pytest

from app.services.ai.base import AIBlocked, AIQuotaExceeded, AIUnavailable

GUEST_IP = "203.0.113.10"


def _generate(client, topic="Started a new job", platform="instagram", ip=GUEST_IP):
    return client.post(
        "/api/captions/generate",
        json={"topic": topic, "platform": platform},
        environ_base={"REMOTE_ADDR": ip},
    )


@pytest.fixture
def tools(captions_repository, ai_provider):
    return captions_repository, ai_provider


# ── Page ────────────────────────────────────────────────────────────────────

def test_guest_can_open_captions_page(client, tools):
    response = client.get("/dashboard/captions", follow_redirects=False)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"


def test_urdu_captions_page_is_rtl(client, tools):
    html = client.get("/ur/dashboard/captions").get_data(as_text=True)
    assert 'dir="rtl"' in html


def test_guest_page_has_no_history_and_shows_login(client, tools):
    html = client.get("/dashboard/captions").get_data(as_text=True)
    assert "data-history" not in html
    assert "/auth/login" in html or "login" in html


def test_logged_in_page_has_history(client, log_in, tools):
    log_in()
    html = client.get("/dashboard/captions").get_data(as_text=True)
    assert "data-history" in html


def test_sidebar_links_to_captions(client, log_in, tools):
    log_in()
    html = client.get("/dashboard").get_data(as_text=True)
    assert 'href="/dashboard/captions"' in html


def test_tool_page_try_button_opens_the_tool(client):
    html = client.get("/tools/captions").get_data(as_text=True)
    assert 'href="/dashboard/captions"' in html


def test_compiled_css_has_the_captions_classes(app):
    import pathlib
    css = (pathlib.Path(app.static_folder) / "css" / "app.css").read_text(encoding="utf-8")
    for selector in (".captions-layout", ".caption-card", ".caption-text", ".history-item", ".captions-topic"):
        assert selector in css


# ── Generate: guests ────────────────────────────────────────────────────────

def test_guest_gets_captions(client, tools):
    repository, ai = tools
    response = _generate(client)
    assert response.status_code == 200
    data = response.get_json()
    assert data["captions"] == ["Caption one #new", "Caption two", "Caption three"]
    assert data["platform"] == "instagram"
    assert data["saved"] is None
    assert data["limit"] == 3
    assert data["remaining"] == 2
    assert "Started a new job" in ai.calls[0]["prompt"]
    assert "Instagram" in ai.calls[0]["prompt"]


def test_linkedin_prompt_is_used_for_linkedin(client, tools):
    _, ai = tools
    _generate(client, platform="LinkedIn")
    assert "LinkedIn" in ai.calls[0]["prompt"]


def test_guest_history_is_never_saved(client, tools):
    repository, _ = tools
    _generate(client)
    assert repository.history == {}


def test_guest_gets_three_tries_per_ip_per_day(client, tools):
    for _ in range(3):
        assert _generate(client).status_code == 200
    response = _generate(client)
    assert response.status_code == 429
    assert response.get_json()["code"] == "limit_guest"
    # Another IP is another guest.
    assert _generate(client, ip="203.0.113.99").status_code == 200


def test_guest_limit_does_not_store_the_raw_ip(client, tools, ai_quota_repository):
    _generate(client)
    assert all(GUEST_IP not in subject for _tool, subject in ai_quota_repository.tries.values())


def test_guest_usage(client, tools):
    _generate(client)
    response = client.get("/api/captions/usage", environ_base={"REMOTE_ADDR": GUEST_IP})
    assert response.get_json() == {"limit": 3, "used": 1, "remaining": 2}


def test_limits_come_from_config(client, app, tools):
    app.config["CAPTIONS_GUEST_DAILY_LIMIT"] = 1
    assert _generate(client).status_code == 200
    assert _generate(client).status_code == 429


# ── Generate: logged-in users ───────────────────────────────────────────────

def test_user_gets_captions_and_history(client, log_in, tools):
    repository, _ = tools
    log_in()
    data = _generate(client).get_json()
    assert data["limit"] == 20
    assert data["remaining"] == 19
    assert data["saved"]["topic"] == "Started a new job"
    history = client.get("/api/captions/history").get_json()["history"]
    assert [row["id"] for row in history] == [data["saved"]["id"]]
    assert history[0]["captions"] == data["captions"]


def test_user_is_counted_by_account_not_ip(client, log_in, app, tools):
    app.config["CAPTIONS_USER_DAILY_LIMIT"] = 2
    log_in()
    assert _generate(client, ip="198.51.100.1").status_code == 200
    assert _generate(client, ip="198.51.100.2").status_code == 200
    response = _generate(client, ip="198.51.100.3")
    assert response.status_code == 429
    assert response.get_json()["code"] == "limit_user"


def test_user_tries_do_not_use_up_guest_tries_on_same_ip(client, log_in, tools, ai_quota_repository):
    log_in()
    _generate(client)
    assert ai_quota_repository.used("captions", ip_hash="anything") == 0
    assert all(subject.startswith("user:") for _tool, subject in ai_quota_repository.tries.values())


def test_history_save_failure_still_returns_captions(client, log_in, tools):
    repository, _ = tools
    repository.history_unavailable = True
    log_in()
    response = _generate(client)
    assert response.status_code == 200
    assert response.get_json()["saved"] is None


# ── Site-wide daily limit ───────────────────────────────────────────────────

def test_site_wide_limit_stops_everyone(client, app, log_in, tools):
    app.config["AI_SITE_DAILY_LIMIT"] = 2
    assert _generate(client, ip="203.0.113.1").status_code == 200
    assert _generate(client, ip="203.0.113.2").status_code == 200
    response = _generate(client, ip="203.0.113.3")
    assert response.status_code == 429
    assert response.get_json()["code"] == "site_limit"
    log_in()
    assert _generate(client).get_json()["code"] == "site_limit"


def test_site_limit_is_sent_to_the_database(client, tools, ai_quota_repository):
    _generate(client)
    assert ai_quota_repository.calls[0][2] == "captions"
    assert ai_quota_repository.calls[0][-1] == 500


def test_site_limit_is_shared_with_other_ai_tools(client, app, tools, ai_quota_repository):
    app.config["AI_SITE_DAILY_LIMIT"] = 1
    ai_quota_repository.tries["other"] = ("cv_writer", "ip:someone-else")
    assert _generate(client).get_json()["code"] == "site_limit"


# ── Validation ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("topic, code", [("", "topic_required"), ("   ", "topic_required"), ("x" * 501, "topic_too_long"), (None, "topic_required")])
def test_bad_topic(client, tools, ai_quota_repository, topic, code):
    _, ai = tools
    response = _generate(client, topic=topic)
    assert response.status_code == 400
    assert response.get_json()["code"] == code
    assert ai_quota_repository.tries == {} and ai.calls == []


def test_bad_platform(client, tools):
    response = _generate(client, platform="tiktok")
    assert response.status_code == 400
    assert response.get_json()["code"] == "platform_invalid"


def test_error_messages_are_translated(client, tools):
    response = client.post("/ur/api/captions/generate", json={"topic": "", "platform": "instagram"})
    assert response.get_json()["message"] != "Please type a topic."


# ── AI failures give the try back ───────────────────────────────────────────

@pytest.mark.parametrize("error, code, status", [
    (AIQuotaExceeded(), "ai_quota", 503),
    (AIUnavailable(), "ai_unavailable", 503),
    (AIBlocked(), "ai_blocked", 422),
])
def test_ai_failure_refunds_the_try(client, tools, ai_quota_repository, error, code, status):
    _, ai = tools
    ai.error = error
    response = _generate(client)
    assert response.status_code == status
    assert response.get_json()["code"] == code
    assert ai_quota_repository.tries == {}


def test_ai_answer_without_captions_is_an_error_and_refunded(client, tools, ai_quota_repository):
    _, ai = tools
    ai.result = {"captions": ["", "   ", 5]}
    response = _generate(client)
    assert response.get_json()["code"] == "ai_unavailable"
    assert ai_quota_repository.tries == {}


def test_ai_answer_is_cleaned(client, tools):
    _, ai = tools
    ai.result = {"captions": ["  one  ", "one", "two", "three", "four"]}
    assert _generate(client).get_json()["captions"] == ["one", "two", "three"]


def test_supabase_down_is_friendly(client, tools, ai_quota_repository):
    _, ai = tools
    ai_quota_repository.unavailable = True
    response = _generate(client)
    assert response.status_code == 503
    assert response.get_json()["code"] == "unavailable"
    assert ai.calls == []


# ── History ─────────────────────────────────────────────────────────────────

def test_history_requires_login(client, tools):
    response = client.get("/api/captions/history")
    assert response.status_code == 401
    assert response.get_json()["code"] == "login_required"


def test_delete_history_requires_login(client, tools):
    assert client.delete("/api/captions/history/00000000-0000-0000-0000-000000000000").status_code == 401


def test_delete_history(client, log_in, tools):
    log_in()
    saved = _generate(client).get_json()["saved"]
    assert client.delete(f"/api/captions/history/{saved['id']}").status_code == 204
    assert client.get("/api/captions/history").get_json()["history"] == []
    assert client.delete(f"/api/captions/history/{saved['id']}").status_code == 404


def test_users_never_see_each_others_history(client, log_in, tools):
    log_in("sara@example.com")
    saved = _generate(client).get_json()["saved"]
    log_in("ali@example.com", name="Ali")
    assert client.get("/api/captions/history").get_json()["history"] == []
    assert client.delete(f"/api/captions/history/{saved['id']}").status_code == 404


def test_delete_bad_id_is_404(client, log_in, tools):
    log_in()
    assert client.delete("/api/captions/history/not-an-id!").status_code == 404


# ── CSRF ────────────────────────────────────────────────────────────────────

def test_generate_needs_csrf_token(client, app, tools):
    app.config["WTF_CSRF_ENABLED"] = True
    response = _generate(client)
    assert response.status_code == 400
    assert tools[1].calls == []
