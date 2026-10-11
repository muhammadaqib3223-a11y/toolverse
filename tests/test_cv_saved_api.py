"""Saved CVs (logged-in users): list, create, open, save, delete, limits and moving guest CVs
into the account. Uses the fake repository only (tests/fakes.py), never Supabase."""
import uuid

import pytest


def _payload(**overrides):
    payload = {
        "title": "Data jobs",
        "template": "minimal",
        "accent": "teal",
        "language": "en",
        "cv": {
            "personal": {"full_name": "Sara Khan", "email": "sara@example.com"},
            "summary": "Analyst.",
            "experience": [{"job_title": "Analyst", "company": "Daraz", "current": True}],
            "skills": ["Python"],
        },
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def user(client, log_in, cvs_repository):
    log_in()
    return cvs_repository


# ── Guests ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("method, url", [
    ("get", "/api/cvs"),
    ("post", "/api/cvs"),
    ("get", f"/api/cvs/{uuid.uuid4()}"),
    ("patch", f"/api/cvs/{uuid.uuid4()}"),
    ("delete", f"/api/cvs/{uuid.uuid4()}"),
    ("post", "/api/cvs/import"),
])
def test_guests_get_json_login_required(client, cvs_repository, method, url):
    response = getattr(client, method)(url, json={})
    assert response.status_code == 401
    assert response.get_json()["code"] == "login_required"


def test_guest_page_still_works_without_login(client, cvs_repository):
    html = client.get("/dashboard/cv-generator").get_data(as_text=True)
    assert 'data-logged-in="false"' in html


# ── Create, list, open, save, delete ────────────────────────────────────────

def test_create_then_list_and_open(client, user):
    created = client.post("/api/cvs", json=_payload())
    assert created.status_code == 201
    cv = created.get_json()["cv"]
    assert cv["title"] == "Data jobs"
    assert cv["template"] == "minimal" and cv["accent"] == "teal"
    assert cv["cv"]["personal"]["full_name"] == "Sara Khan"

    listed = client.get("/api/cvs").get_json()["cvs"]
    assert [item["id"] for item in listed] == [cv["id"]]
    assert "cv" not in listed[0]  # the list is light; the form comes with GET /api/cvs/<id>

    opened = client.get(f"/api/cvs/{cv['id']}").get_json()["cv"]
    assert opened["cv"]["experience"][0]["company"] == "Daraz"


def test_unfinished_cv_can_be_saved_without_a_name(client, user):
    response = client.post("/api/cvs", json=_payload(title="", cv={"summary": "Draft"}))
    assert response.status_code == 201
    assert response.get_json()["cv"]["title"] == "CV"


def test_title_defaults_to_the_name(client, user):
    response = client.post("/api/cvs", json=_payload(title="  "))
    assert response.get_json()["cv"]["title"] == "Sara Khan"


def test_saved_data_is_cleaned(client, user):
    cv = _payload()["cv"]
    cv["skills"] = ["Python", "python", " "]
    cv["experience"].append({})
    saved = client.post("/api/cvs", json=_payload(cv=cv)).get_json()["cv"]["cv"]
    assert saved["skills"] == ["Python"]
    assert len(saved["experience"]) == 1


def test_update_saves_changes(client, user):
    cv_id = client.post("/api/cvs", json=_payload()).get_json()["cv"]["id"]
    response = client.patch(f"/api/cvs/{cv_id}", json=_payload(title="Banking", template="executive", accent="maroon"))
    assert response.status_code == 200
    updated = response.get_json()["cv"]
    assert (updated["title"], updated["template"], updated["accent"]) == ("Banking", "executive", "maroon")


def test_delete(client, user):
    cv_id = client.post("/api/cvs", json=_payload()).get_json()["cv"]["id"]
    assert client.delete(f"/api/cvs/{cv_id}").status_code == 204
    assert client.get(f"/api/cvs/{cv_id}").status_code == 404
    assert client.delete(f"/api/cvs/{cv_id}").status_code == 404


def test_users_cannot_see_each_others_cvs(client, log_in, cvs_repository):
    log_in("sara@example.com")
    cv_id = client.post("/api/cvs", json=_payload()).get_json()["cv"]["id"]
    log_in("ali@example.com", name="Ali")
    assert client.get("/api/cvs").get_json()["cvs"] == []
    assert client.get(f"/api/cvs/{cv_id}").status_code == 404
    assert client.patch(f"/api/cvs/{cv_id}", json=_payload()).status_code == 404
    assert client.delete(f"/api/cvs/{cv_id}").status_code == 404


@pytest.mark.parametrize("bad_id", ["not-a-uuid", "123", "' or 1=1 --"])
def test_bad_ids_are_not_found(client, user, bad_id):
    assert client.get(f"/api/cvs/{bad_id}").status_code == 404


@pytest.mark.parametrize("payload, code, field", [
    (_payload(template="fancy"), "template_invalid", "template"),
    (_payload(accent="pink"), "accent_invalid", "accent"),
    (_payload(language="fr"), "language_invalid", "language"),
    (_payload(title="x" * 121), "title_too_long", "title"),
    (_payload(cv={"personal": {"email": "nope"}}), "email_invalid", "personal.email"),
    (_payload(cv="text"), "invalid_data", None),
])
def test_bad_saves_give_clear_errors(client, user, payload, code, field):
    response = client.post("/api/cvs", json=payload)
    assert response.status_code == 400
    body = response.get_json()
    assert (body["code"], body["field"]) == (code, field)


def test_cv_limit(client, user):
    user.max_cvs = 2
    client.post("/api/cvs", json=_payload())
    client.post("/api/cvs", json=_payload())
    response = client.post("/api/cvs", json=_payload())
    assert response.status_code == 409
    assert response.get_json()["code"] == "cv_limit"


def test_supabase_down_gives_friendly_error(client, user):
    user.unavailable = True
    response = client.get("/api/cvs")
    assert response.status_code == 503
    assert response.get_json()["code"] == "unavailable"


def test_save_needs_csrf_token(client, app, user):
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post("/api/cvs", json=_payload()).status_code == 400


# ── Moving guest CVs into the account ───────────────────────────────────────

def _guest_cv(**overrides):
    item = {"id": str(uuid.uuid4()), **_payload(), "updatedAt": 1}
    item.update(overrides)
    return item


def test_import_moves_guest_cvs_once(client, user):
    guest = [_guest_cv(), _guest_cv(title="Second")]
    first = client.post("/api/cvs/import", json={"cvs": guest})
    assert first.status_code == 200
    assert len(first.get_json()["cvs"]) == 2
    again = client.post("/api/cvs/import", json={"cvs": guest})
    assert again.get_json()["cvs"] == []  # retrying never duplicates
    assert len(client.get("/api/cvs").get_json()["cvs"]) == 2


def test_import_skips_bad_items_and_respects_the_limit(client, user):
    from app.blueprints.tools.cv_generator.saved_cvs import MAX_SAVED_CVS
    for _ in range(MAX_SAVED_CVS - 1):
        client.post("/api/cvs", json=_payload())
    guest = [_guest_cv(id="not-a-uuid"), _guest_cv(template="fancy"), _guest_cv(), _guest_cv(), "junk"]
    response = client.post("/api/cvs/import", json={"cvs": guest})
    assert response.status_code == 200
    assert len(response.get_json()["cvs"]) == 1  # only room for one more


def test_logged_in_page_offers_to_move_guest_cvs(client, user):
    html = client.get("/dashboard/cv-generator").get_data(as_text=True)
    assert 'data-logged-in="true"' in html
    assert 'data-guest-key="toolverse_guest_cvs"' in html
    assert 'data-api-import="/api/cvs/import"' in html
