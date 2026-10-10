"""Business rules for expenses: validation and limits. Routes call these, never the repository directly."""
import re
from datetime import date, datetime

from app.blueprints.tools.expenses.errors import ExpenseError, ExpenseNotFound
from app.blueprints.tools.expenses.repository import get_repository

DESCRIPTION_MAX_LENGTH = 200
CURRENCY_DEFAULT = "PKR"
SUPPORTED_CURRENCIES = ("PKR", "USD", "EUR", "GBP", "AED", "SAR", "INR")

_ID_RE = re.compile(r"^[0-9a-fA-F-]{8,36}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def list_month(access_token, year, month):
    """(expenses, monthly_total) for the given year-month."""
    expenses = get_repository().list_month(access_token, year, month)
    total = sum(float(exp["amount"]) for exp in expenses)
    return expenses, round(total, 2)


def create_expense(access_token, amount, description, currency, spent_at, client_id=None):
    amount, description, currency, spent_at = _validate(amount, description, currency, spent_at)
    return get_repository().insert_expense(access_token, amount, description, currency, spent_at, client_id=client_id)


def update_expense(access_token, expense_id, amount, description, currency, spent_at):
    _validate_id(expense_id)
    amount, description, currency, spent_at = _validate(amount, description, currency, spent_at)
    expense = get_repository().update_expense(access_token, expense_id, amount, description, currency, spent_at)
    if expense is None:
        raise ExpenseNotFound()
    return expense


def delete_expense(access_token, expense_id):
    _validate_id(expense_id)
    if not get_repository().delete_expense(access_token, expense_id):
        raise ExpenseNotFound()


def set_currency_preference(auth_session, currency):
    """Save the user's preferred currency in their Supabase user_metadata."""
    currency = (currency or CURRENCY_DEFAULT).strip().upper()
    if currency not in SUPPORTED_CURRENCIES:
        raise ExpenseError("currency_invalid")
    from app.blueprints.auth.services import get_auth_service  # avoid circular at module level
    get_auth_service().update_user_metadata(auth_session, {"expense_currency": currency})
    return currency


def import_expenses(access_token, guest_expenses):
    """Move guest expenses into the account. Safe to retry — duplicate client_ids are skipped."""
    rows = []
    for exp in guest_expenses if isinstance(guest_expenses, list) else []:
        if not isinstance(exp, dict):
            continue
        client_id = str(exp.get("id") or "").strip()
        if not client_id:
            continue
        try:
            amount, description, currency, spent_at = _validate(
                exp.get("amount"), exp.get("description", ""), exp.get("currency"), exp.get("spentAt")
            )
        except ExpenseError:
            continue
        rows.append({
            "amount": str(amount),
            "description": description,
            "currency": currency,
            "spent_at": spent_at,
            "client_id": client_id,
        })
    if not rows:
        return []
    return get_repository().import_expenses(access_token, rows)


def _validate(amount, description, currency, spent_at):
    # amount
    try:
        amount = float(str(amount or "").strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        raise ExpenseError("amount_invalid") from None
    if not amount:
        raise ExpenseError("amount_required")

    # description
    description = (description or "").strip()
    if not description:
        raise ExpenseError("description_required")
    if len(description) > DESCRIPTION_MAX_LENGTH:
        raise ExpenseError("description_too_long")

    # currency
    currency = (currency or CURRENCY_DEFAULT).strip().upper() or CURRENCY_DEFAULT

    # spent_at — accept a YYYY-MM-DD string or fall back to today
    spent_at = (str(spent_at or "")).strip()
    if spent_at and not _DATE_RE.match(spent_at):
        raise ExpenseError("date_invalid")
    if not spent_at:
        spent_at = date.today().isoformat()
    else:
        try:
            datetime.strptime(spent_at, "%Y-%m-%d")
        except ValueError:
            raise ExpenseError("date_invalid") from None

    return amount, description, currency, spent_at


def _validate_id(expense_id):
    if not expense_id or not _ID_RE.match(str(expense_id)):
        raise ExpenseNotFound()
