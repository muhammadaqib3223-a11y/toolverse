"""The Notes page and its JSON API."""
import json


def _json(response):
    return json.loads(response.get_data(as_text=True))


# --- The page: guests and logged-in users can both open it ---

def test_guest_can_open_the_notes_page(client, notes_repository):
    response = client.get("/dashboard/notes")
    assert response.status_code == 200


def test_guest_notes_page_is_not_a_redirect(client, notes_repository):
    response = client.get("/dashboard/notes", follow_redirects=False)
    assert response.status_code == 200


def test_guest_can_open_urdu_notes_page(client, notes_repository):
    assert client.get("/ur/dashboard/notes").status_code == 200


def test_logged_in_user_can_open_the_notes_page(client, log_in, notes_repository):
    log_in()
    response = client.get("/dashboard/notes")
    assert response.status_code == 200


def test_notes_page_is_private(client, log_in, notes_repository):
    log_in()
    response = client.get("/dashboard/notes")
    assert response.headers["Cache-Control"] == "private, no-store"


def test_notes_page_in_urdu(client, notes_repository):
    html = client.get("/ur/dashboard/notes").get_data(as_text=True)
    assert 'dir="rtl"' in html


def test_sidebar_shows_notes_as_live(client, log_in, notes_repository):
    log_in()
    html = client.get("/dashboard").get_data(as_text=True)
    assert 'href="/dashboard/notes"' in html


# --- The API requires login ---

def test_api_list_requires_login(client, notes_repository):
    response = client.get("/api/notes")
    assert response.status_code == 401
    assert _json(response)["code"] == "login_required"


def test_api_create_requires_login(client, notes_repository):
    response = client.post("/api/notes", json={"title": "Hi", "content": ""})
    assert response.status_code == 401


# --- Create, list, update, delete ---

def test_create_note(client, log_in, notes_repository):
    log_in()
    response = client.post("/api/notes", json={"title": "Shopping list", "content": "Milk"})
    assert response.status_code == 201
    note = _json(response)["note"]
    assert note["title"] == "Shopping list"
    assert note["content"] == "Milk"
    assert "id" in note


def test_create_note_without_title_is_a_bad_request(client, log_in, notes_repository):
    log_in()
    response = client.post("/api/notes", json={"title": "  ", "content": ""})
    assert response.status_code == 400
    assert _json(response)["code"] == "title_required"


def test_create_note_title_too_long_is_a_bad_request(client, log_in, notes_repository):
    log_in()
    response = client.post("/api/notes", json={"title": "x" * 201, "content": ""})
    assert response.status_code == 400
    assert _json(response)["code"] == "title_too_long"


def test_list_notes(client, log_in, notes_repository):
    log_in()
    client.post("/api/notes", json={"title": "First", "content": ""})
    client.post("/api/notes", json={"title": "Second", "content": ""})
    response = client.get("/api/notes")
    data = _json(response)
    assert len(data["notes"]) == 2
    assert data["has_more"] is False


def test_list_notes_search(client, log_in, notes_repository):
    log_in()
    client.post("/api/notes", json={"title": "Meeting notes", "content": "budget talk"})
    client.post("/api/notes", json={"title": "Shopping", "content": "milk"})
    response = client.get("/api/notes?search=budget")
    notes = _json(response)["notes"]
    assert len(notes) == 1
    assert notes[0]["title"] == "Meeting notes"

    response = client.get("/api/notes?search=nothing")
    assert _json(response)["notes"] == []


def test_update_note(client, log_in, notes_repository):
    log_in()
    created = _json(client.post("/api/notes", json={"title": "Old", "content": ""}))["note"]
    response = client.patch(f"/api/notes/{created['id']}", json={"title": "New", "content": "Updated"})
    assert response.status_code == 200
    note = _json(response)["note"]
    assert note["title"] == "New"
    assert note["content"] == "Updated"


def test_update_missing_note_is_404(client, log_in, notes_repository):
    log_in()
    response = client.patch("/api/notes/00000000-0000-0000-0000-000000000000", json={"title": "New", "content": ""})
    assert response.status_code == 404
    assert _json(response)["code"] == "not_found"


def test_delete_note(client, log_in, notes_repository):
    log_in()
    created = _json(client.post("/api/notes", json={"title": "Bye", "content": ""}))["note"]
    response = client.delete(f"/api/notes/{created['id']}")
    assert response.status_code == 204
    assert _json(client.get("/api/notes"))["notes"] == []


def test_delete_missing_note_is_404(client, log_in, notes_repository):
    log_in()
    response = client.delete("/api/notes/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_a_user_cannot_see_another_users_note(client, log_in, notes_repository):
    log_in(email="first@example.com")
    created = _json(client.post("/api/notes", json={"title": "Private", "content": ""}))["note"]

    log_in(email="second@example.com")  # log_in() replaces the session cookie with this user's
    response = client.get("/api/notes")
    assert _json(response)["notes"] == []

    response = client.patch(f"/api/notes/{created['id']}", json={"title": "Stolen", "content": ""})
    assert response.status_code == 404


# --- Moving guest notes into the account ---

def test_import_creates_notes(client, log_in, notes_repository):
    log_in()
    guest_notes = [
        {"id": "guest-1", "title": "First", "content": "a"},
        {"id": "guest-2", "title": "Second", "content": "b"},
    ]
    response = client.post("/api/notes/import", json={"notes": guest_notes})
    assert response.status_code == 200
    assert len(_json(response)["notes"]) == 2
    assert len(_json(client.get("/api/notes"))["notes"]) == 2


def test_import_twice_does_not_duplicate(client, log_in, notes_repository):
    log_in()
    guest_notes = [{"id": "guest-1", "title": "First", "content": "a"}]
    client.post("/api/notes/import", json={"notes": guest_notes})
    client.post("/api/notes/import", json={"notes": guest_notes})
    assert len(_json(client.get("/api/notes"))["notes"]) == 1


def test_import_requires_login(client, notes_repository):
    response = client.post("/api/notes/import", json={"notes": []})
    assert response.status_code == 401


# --- CSRF: the API is POST/PATCH/DELETE, so it is protected like every other form in the app ---

def test_create_note_without_csrf_token_is_rejected(client, log_in, notes_repository, app):
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        log_in()
        response = client.post("/api/notes", json={"title": "Hi", "content": ""})
        assert response.status_code == 400
        assert _json(response)["code"] == "csrf_failed"
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


# --- Friendly, translated error messages ---

def test_error_messages_are_in_urdu_on_urdu_pages(client, log_in, notes_repository):
    log_in()
    response = client.patch("/ur/api/notes/00000000-0000-0000-0000-000000000000", json={"title": "x", "content": ""})
    assert response.status_code == 404
    message = _json(response)["message"]
    assert message != ""
    assert message != "That note no longer exists."
