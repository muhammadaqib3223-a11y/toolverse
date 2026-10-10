"""Unit tests for expenses business rules (validation, totals) — no HTTP, no Supabase."""
import pytest

from app.blueprints.tools.expenses import services
from app.blueprints.tools.expenses.errors import ExpenseError, ExpenseNotFound, ExpensesUnavailable

TOKEN = "access-1"
TODAY = "2026-10-10"
MONTH = (2026, 10)


@pytest.fixture
def ctx(app, expenses_repository):
    with app.app_context():
        yield expenses_repository


def _make(ctx, amount="100", description="Groceries", spent_at=TODAY):
    return services.create_expense(TOKEN, amount, description, "PKR", spent_at)


# ── Create ─────────────────────────────────────────────────────────────────

def test_create_returns_the_saved_expense(ctx):
    exp = _make(ctx)
    assert float(exp["amount"]) == 100.0
    assert exp["description"] == "Groceries"
    assert exp["currency"] == "PKR"
    assert exp["spent_at"] == TODAY
    assert exp["id"]


def test_create_trims_description(ctx):
    exp = services.create_expense(TOKEN, "50", "  Lunch  ", "PKR", TODAY)
    assert exp["description"] == "Lunch"


def test_create_without_amount_fails(ctx):
    with pytest.raises(ExpenseError) as exc:
        services.create_expense(TOKEN, "", "Lunch", "PKR", TODAY)
    assert exc.value.code == "amount_invalid"


def test_create_with_zero_amount_fails(ctx):
    with pytest.raises(ExpenseError) as exc:
        services.create_expense(TOKEN, "0", "Lunch", "PKR", TODAY)
    assert exc.value.code == "amount_invalid"


def test_create_with_negative_amount_fails(ctx):
    with pytest.raises(ExpenseError) as exc:
        services.create_expense(TOKEN, "-5", "Lunch", "PKR", TODAY)
    assert exc.value.code == "amount_invalid"


def test_create_without_description_fails(ctx):
    with pytest.raises(ExpenseError) as exc:
        services.create_expense(TOKEN, "10", "   ", "PKR", TODAY)
    assert exc.value.code == "description_required"


def test_create_description_too_long_fails(ctx):
    with pytest.raises(ExpenseError) as exc:
        services.create_expense(TOKEN, "10", "x" * 201, "PKR", TODAY)
    assert exc.value.code == "description_too_long"


def test_create_with_invalid_date_fails(ctx):
    with pytest.raises(ExpenseError) as exc:
        services.create_expense(TOKEN, "10", "Lunch", "PKR", "not-a-date")
    assert exc.value.code == "date_invalid"


def test_create_without_date_defaults_to_today(ctx):
    exp = services.create_expense(TOKEN, "10", "Lunch", "PKR", "")
    assert exp["spent_at"]  # some date was set


def test_create_normalises_currency_to_uppercase(ctx):
    exp = services.create_expense(TOKEN, "10", "Lunch", "usd", TODAY)
    assert exp["currency"] == "USD"


# ── List month + total ──────────────────────────────────────────────────────

def test_list_month_returns_only_that_month(ctx):
    _make(ctx, spent_at="2026-10-05")
    _make(ctx, spent_at="2026-09-30")
    expenses, _ = services.list_month(TOKEN, *MONTH)
    assert len(expenses) == 1
    assert expenses[0]["spent_at"] == "2026-10-05"


def test_monthly_total_is_sum_of_amounts(ctx):
    _make(ctx, amount="100", spent_at="2026-10-01")
    _make(ctx, amount="50.5", spent_at="2026-10-15")
    _, total = services.list_month(TOKEN, *MONTH)
    assert total == 150.5


def test_monthly_total_is_zero_when_no_expenses(ctx):
    _, total = services.list_month(TOKEN, *MONTH)
    assert total == 0


# ── Update ─────────────────────────────────────────────────────────────────

def test_update_changes_fields(ctx):
    exp = _make(ctx)
    updated = services.update_expense(TOKEN, exp["id"], "200", "Transport", "USD", "2026-10-02")
    assert float(updated["amount"]) == 200.0
    assert updated["description"] == "Transport"
    assert updated["currency"] == "USD"
    assert updated["spent_at"] == "2026-10-02"


def test_update_missing_expense_raises_not_found(ctx):
    with pytest.raises(ExpenseNotFound):
        services.update_expense(TOKEN, "00000000-0000-0000-0000-000000000000", "10", "x", "PKR", TODAY)


def test_update_malformed_id_raises_not_found(ctx):
    with pytest.raises(ExpenseNotFound):
        services.update_expense(TOKEN, "not-a-uuid", "10", "x", "PKR", TODAY)


def test_update_another_users_expense_raises_not_found(ctx):
    exp = _make(ctx)
    with pytest.raises(ExpenseNotFound):
        services.update_expense("access-2", exp["id"], "10", "x", "PKR", TODAY)


# ── Delete ─────────────────────────────────────────────────────────────────

def test_delete_removes_the_expense(ctx):
    exp = _make(ctx)
    services.delete_expense(TOKEN, exp["id"])
    expenses, _ = services.list_month(TOKEN, *MONTH)
    assert expenses == []


def test_delete_missing_expense_raises_not_found(ctx):
    with pytest.raises(ExpenseNotFound):
        services.delete_expense(TOKEN, "00000000-0000-0000-0000-000000000000")


# ── Import ─────────────────────────────────────────────────────────────────

def test_import_creates_each_expense(ctx):
    guest = [
        {"id": "g-1", "amount": "100", "description": "Lunch",  "currency": "PKR", "spentAt": TODAY},
        {"id": "g-2", "amount": "200", "description": "Dinner", "currency": "PKR", "spentAt": TODAY},
    ]
    imported = services.import_expenses(TOKEN, guest)
    assert len(imported) == 2
    expenses, _ = services.list_month(TOKEN, *MONTH)
    assert len(expenses) == 2


def test_import_is_safe_to_retry(ctx):
    guest = [{"id": "g-1", "amount": "100", "description": "Lunch", "currency": "PKR", "spentAt": TODAY}]
    services.import_expenses(TOKEN, guest)
    services.import_expenses(TOKEN, guest)
    expenses, _ = services.list_month(TOKEN, *MONTH)
    assert len(expenses) == 1


def test_import_skips_invalid_entries(ctx):
    guest = [
        {"id": "g-1", "amount": "0",   "description": "Bad",  "currency": "PKR", "spentAt": TODAY},
        {"id": "g-2", "amount": "100", "description": "",     "currency": "PKR", "spentAt": TODAY},
        {"id": "g-3", "amount": "50",  "description": "Good", "currency": "PKR", "spentAt": TODAY},
    ]
    imported = services.import_expenses(TOKEN, guest)
    assert len(imported) == 1
    assert imported[0]["description"] == "Good"


def test_import_with_empty_list_returns_empty(ctx):
    assert services.import_expenses(TOKEN, []) == []


# ── Isolation ──────────────────────────────────────────────────────────────

def test_two_users_expenses_never_mix(ctx):
    services.create_expense("access-1", "100", "Mine", "PKR", TODAY)
    services.create_expense("access-2", "200", "Theirs", "PKR", TODAY)
    e1, _ = services.list_month("access-1", *MONTH)
    e2, _ = services.list_month("access-2", *MONTH)
    assert [e["description"] for e in e1] == ["Mine"]
    assert [e["description"] for e in e2] == ["Theirs"]


# ── Unavailable repository ─────────────────────────────────────────────────

def test_unavailable_repository_raises(app, expenses_repository):
    expenses_repository.unavailable = True
    with app.app_context():
        with pytest.raises(ExpensesUnavailable):
            services.list_month(TOKEN, *MONTH)
