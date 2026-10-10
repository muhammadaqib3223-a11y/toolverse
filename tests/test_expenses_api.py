"""HTTP routes for the Expense Tracker."""
import json


def _json(response):
    return json.loads(response.get_data(as_text=True))


TODAY = "2026-10-10"


# ── Page: guests and logged-in users can both open it ─────────────────────

def test_guest_can_open_expenses_page(client, expenses_repository):
    assert client.get("/dashboard/expenses").status_code == 200


def test_guest_can_open_expenses_page_without_auth_service(client, expenses_repository):
    # Proves the page never redirects to login; does NOT swap the auth service,
    # to catch regressions where a before_request hook might redirect guests.
    assert client.get("/dashboard/expenses").status_code == 200


def test_guest_expenses_page_is_not_a_redirect(client, expenses_repository):
    response = client.get("/dashboard/expenses", follow_redirects=False)
    assert response.status_code == 200


def test_guest_can_open_urdu_expenses_page(client, expenses_repository):
    assert client.get("/ur/dashboard/expenses").status_code == 200


def test_logged_in_user_can_open_expenses_page(client, log_in, expenses_repository):
    log_in()
    assert client.get("/dashboard/expenses").status_code == 200


def test_expenses_page_is_private(client, log_in, expenses_repository):
    log_in()
    response = client.get("/dashboard/expenses")
    assert response.headers["Cache-Control"] == "private, no-store"


def test_expenses_page_in_urdu(client, expenses_repository):
    html = client.get("/ur/dashboard/expenses").get_data(as_text=True)
    assert 'dir="rtl"' in html


def test_sidebar_shows_expenses_as_live(client, log_in, expenses_repository):
    log_in()
    html = client.get("/dashboard").get_data(as_text=True)
    assert 'href="/dashboard/expenses"' in html


# ── API requires login ────────────────────────────────────────────────────

def test_api_list_requires_login(client, expenses_repository):
    response = client.get("/api/expenses")
    assert response.status_code == 401
    assert _json(response)["code"] == "login_required"


def test_api_create_requires_login(client, expenses_repository):
    response = client.post("/api/expenses", json={"amount": "100", "description": "Lunch", "currency": "PKR", "spent_at": TODAY})
    assert response.status_code == 401


# ── Create ─────────────────────────────────────────────────────────────────

def test_create_expense(client, log_in, expenses_repository):
    log_in()
    response = client.post("/api/expenses", json={"amount": "150", "description": "Transport", "currency": "PKR", "spent_at": TODAY})
    assert response.status_code == 201
    exp = _json(response)["expense"]
    assert float(exp["amount"]) == 150.0
    assert exp["description"] == "Transport"
    assert exp["id"]


def test_create_without_amount_is_400(client, log_in, expenses_repository):
    log_in()
    response = client.post("/api/expenses", json={"amount": "0", "description": "Bad", "currency": "PKR", "spent_at": TODAY})
    assert response.status_code == 400
    assert _json(response)["code"] == "amount_invalid"


def test_create_without_description_is_400(client, log_in, expenses_repository):
    log_in()
    response = client.post("/api/expenses", json={"amount": "10", "description": "", "currency": "PKR", "spent_at": TODAY})
    assert response.status_code == 400
    assert _json(response)["code"] == "description_required"


# ── List ─────────────────────────────────────────────────────────────────

def test_list_expenses_returns_current_month(client, log_in, expenses_repository):
    log_in()
    client.post("/api/expenses", json={"amount": "100", "description": "Lunch", "currency": "PKR", "spent_at": "2026-10-01"})
    client.post("/api/expenses", json={"amount": "200", "description": "Dinner", "currency": "PKR", "spent_at": "2026-10-02"})
    data = _json(client.get("/api/expenses?year=2026&month=10"))
    assert len(data["expenses"]) == 2
    assert data["total"] == 300.0


def test_list_expenses_excludes_other_months(client, log_in, expenses_repository):
    log_in()
    client.post("/api/expenses", json={"amount": "100", "description": "Oct", "currency": "PKR", "spent_at": "2026-10-01"})
    client.post("/api/expenses", json={"amount": "200", "description": "Sep", "currency": "PKR", "spent_at": "2026-09-30"})
    data = _json(client.get("/api/expenses?year=2026&month=10"))
    assert len(data["expenses"]) == 1
    assert data["expenses"][0]["description"] == "Oct"


def test_total_is_zero_for_empty_month(client, log_in, expenses_repository):
    log_in()
    data = _json(client.get("/api/expenses?year=2025&month=1"))
    assert data["expenses"] == []
    assert data["total"] == 0


# ── Update ─────────────────────────────────────────────────────────────────

def test_update_expense(client, log_in, expenses_repository):
    log_in()
    created = _json(client.post("/api/expenses", json={"amount": "100", "description": "Old", "currency": "PKR", "spent_at": TODAY}))["expense"]
    response = client.patch(f"/api/expenses/{created['id']}", json={"amount": "200", "description": "New", "currency": "PKR", "spent_at": TODAY})
    assert response.status_code == 200
    updated = _json(response)["expense"]
    assert float(updated["amount"]) == 200.0
    assert updated["description"] == "New"


def test_update_missing_expense_is_404(client, log_in, expenses_repository):
    log_in()
    response = client.patch("/api/expenses/00000000-0000-0000-0000-000000000000", json={"amount": "10", "description": "x", "currency": "PKR", "spent_at": TODAY})
    assert response.status_code == 404
    assert _json(response)["code"] == "not_found"


# ── Delete ─────────────────────────────────────────────────────────────────

def test_delete_expense(client, log_in, expenses_repository):
    log_in()
    created = _json(client.post("/api/expenses", json={"amount": "100", "description": "Bye", "currency": "PKR", "spent_at": TODAY}))["expense"]
    response = client.delete(f"/api/expenses/{created['id']}")
    assert response.status_code == 204
    data = _json(client.get("/api/expenses?year=2026&month=10"))
    assert data["expenses"] == []


def test_delete_missing_expense_is_404(client, log_in, expenses_repository):
    log_in()
    response = client.delete("/api/expenses/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


# ── Isolation ─────────────────────────────────────────────────────────────

def test_user_cannot_see_another_users_expense(client, log_in, expenses_repository):
    log_in(email="first@example.com")
    created = _json(client.post("/api/expenses", json={"amount": "100", "description": "Private", "currency": "PKR", "spent_at": TODAY}))["expense"]

    log_in(email="second@example.com")
    data = _json(client.get("/api/expenses?year=2026&month=10"))
    assert data["expenses"] == []

    response = client.patch(f"/api/expenses/{created['id']}", json={"amount": "1", "description": "Stolen", "currency": "PKR", "spent_at": TODAY})
    assert response.status_code == 404


# ── Guest import ──────────────────────────────────────────────────────────

def test_import_expenses(client, log_in, expenses_repository):
    log_in()
    guest = [
        {"id": "g-1", "amount": "100", "description": "Lunch",  "currency": "PKR", "spentAt": TODAY},
        {"id": "g-2", "amount": "200", "description": "Dinner", "currency": "PKR", "spentAt": TODAY},
    ]
    response = client.post("/api/expenses/import", json={"expenses": guest})
    assert response.status_code == 200
    assert len(_json(response)["expenses"]) == 2


def test_import_twice_does_not_duplicate(client, log_in, expenses_repository):
    log_in()
    guest = [{"id": "g-1", "amount": "100", "description": "Lunch", "currency": "PKR", "spentAt": TODAY}]
    client.post("/api/expenses/import", json={"expenses": guest})
    client.post("/api/expenses/import", json={"expenses": guest})
    data = _json(client.get("/api/expenses?year=2026&month=10"))
    assert len(data["expenses"]) == 1


def test_import_requires_login(client, expenses_repository):
    response = client.post("/api/expenses/import", json={"expenses": []})
    assert response.status_code == 401


# ── CSRF ──────────────────────────────────────────────────────────────────

def test_create_without_csrf_is_rejected(client, log_in, expenses_repository, app):
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        log_in()
        response = client.post("/api/expenses", json={"amount": "10", "description": "x", "currency": "PKR", "spent_at": TODAY})
        assert response.status_code == 400
        assert _json(response)["code"] == "csrf_failed"
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


# ── Urdu error messages ───────────────────────────────────────────────────

def test_error_messages_are_in_urdu_on_urdu_pages(client, log_in, expenses_repository):
    log_in()
    response = client.patch("/ur/api/expenses/00000000-0000-0000-0000-000000000000", json={"amount": "10", "description": "x", "currency": "PKR", "spent_at": TODAY})
    assert response.status_code == 404
    message = _json(response)["message"]
    assert message != ""
    assert message != "That expense no longer exists."


# ── Currency preference ────────────────────────────────────────────────────

def test_set_currency_requires_login(client, expenses_repository):
    response = client.post("/api/expenses/currency", json={"currency": "USD"})
    assert response.status_code == 401
    assert _json(response)["code"] == "login_required"


def test_set_currency_saves_preference(client, log_in, expenses_repository):
    log_in()
    response = client.post("/api/expenses/currency", json={"currency": "USD"})
    assert response.status_code == 200
    assert _json(response)["currency"] == "USD"


def test_set_currency_rejects_unknown_currency(client, log_in, expenses_repository):
    log_in()
    response = client.post("/api/expenses/currency", json={"currency": "XYZ"})
    assert response.status_code == 400
    assert _json(response)["code"] == "currency_invalid"


def test_set_currency_normalises_lowercase(client, log_in, expenses_repository):
    log_in()
    response = client.post("/api/expenses/currency", json={"currency": "eur"})
    assert response.status_code == 200
    assert _json(response)["currency"] == "EUR"


def test_logged_in_user_currency_passed_to_template(client, log_in, expenses_repository):
    auth = log_in()
    # After setting the currency, the page should embed it in data-user-currency.
    client.post("/api/expenses/currency", json={"currency": "GBP"})
    # Re-log in so g.user.metadata reflects the updated value stored in FakeUser.
    html = client.get("/dashboard/expenses").get_data(as_text=True)
    assert "GBP" in html


def test_guest_currency_not_in_template(client, expenses_repository):
    html = client.get("/dashboard/expenses").get_data(as_text=True)
    # data-user-currency should be empty for guests.
    assert 'data-user-currency=""' in html
