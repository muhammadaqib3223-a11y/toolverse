"""Expense Tracker: add, edit, delete expenses; monthly total; daily list.

A logged-in user's expenses live in Supabase with Row Level Security.
A guest's expenses stay in the browser until they log in, when the page offers to move them.
"""
from flask import Blueprint

bp = Blueprint("expenses", __name__)

from app.blueprints.tools.expenses import routes  # noqa: E402,F401


def init_expenses(app):
    from app.blueprints.tools.expenses.repository import SupabaseExpensesRepository

    app.extensions["expenses_repository"] = SupabaseExpensesRepository()
