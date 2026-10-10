from datetime import date

from flask import g, jsonify, render_template, request

from app.blueprints.auth.decorators import login_optional
from app.blueprints.auth.session import current_auth_session
from app.blueprints.tools.expenses import bp, services
from app.blueprints.tools.expenses.errors import ExpenseError
from app.blueprints.tools.expenses.messages import error_message
from app.i18n import localized_route

_ERROR_STATUS = {
    "login_required": 401,
    "not_found": 404,
    "unavailable": 503,
}


@localized_route(bp, "/dashboard/expenses", methods=["GET"])
@login_optional
def index():
    user_currency = None
    if g.get("user"):
        user_currency = g.user.metadata.get("expense_currency")
    return render_template("tools/expenses/index.html", active_nav="expenses", user_currency=user_currency)


@localized_route(bp, "/api/expenses", methods=["GET", "POST"])
@login_optional
def api_expenses():
    try:
        access_token = _access_token()
        if request.method == "POST":
            return _create_expense(access_token)
        return _list_expenses(access_token)
    except ExpenseError as error:
        return _error_response(error)


@localized_route(bp, "/api/expenses/<expense_id>", methods=["PATCH", "DELETE"])
@login_optional
def api_expense(expense_id):
    try:
        access_token = _access_token()
        if request.method == "DELETE":
            services.delete_expense(access_token, expense_id)
            return "", 204
        data = request.get_json(silent=True) or {}
        expense = services.update_expense(
            access_token,
            expense_id,
            data.get("amount"),
            data.get("description", ""),
            data.get("currency"),
            data.get("spent_at"),
        )
        return jsonify(expense=expense)
    except ExpenseError as error:
        return _error_response(error)


@localized_route(bp, "/api/expenses/currency", methods=["POST"])
@login_optional
def api_set_currency():
    try:
        if g.get("user") is None:
            raise ExpenseError("login_required")
        auth_session = current_auth_session()
        if auth_session is None:
            raise ExpenseError("login_required")
        data = request.get_json(silent=True) or {}
        currency = services.set_currency_preference(auth_session, data.get("currency"))
        return jsonify(currency=currency)
    except ExpenseError as error:
        return _error_response(error)


@localized_route(bp, "/api/expenses/import", methods=["POST"])
@login_optional
def api_import():
    try:
        access_token = _access_token()
        data = request.get_json(silent=True) or {}
        expenses = services.import_expenses(access_token, data.get("expenses") or [])
        return jsonify(expenses=expenses)
    except ExpenseError as error:
        return _error_response(error)


def _list_expenses(access_token):
    today = date.today()
    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
        if not (1 <= month <= 12):
            raise ValueError
    except (TypeError, ValueError):
        year, month = today.year, today.month
    expenses, total = services.list_month(access_token, year, month)
    return jsonify(expenses=expenses, total=total)


def _create_expense(access_token):
    data = request.get_json(silent=True) or {}
    expense = services.create_expense(
        access_token,
        data.get("amount"),
        data.get("description", ""),
        data.get("currency"),
        data.get("spent_at"),
    )
    return jsonify(expense=expense), 201


def _access_token():
    if g.get("user") is None:
        raise ExpenseError("login_required")
    auth_session = current_auth_session()
    if auth_session is None:
        raise ExpenseError("login_required")
    return auth_session.access_token


def _error_response(error):
    status = _ERROR_STATUS.get(error.code, 400)
    return jsonify(code=error.code, message=str(error_message(error))), status
