"""Talks to the `expenses` table in Supabase, as the signed-in user named by `access_token`.

Row Level Security keeps every user's expenses private (see supabase/migrations/20261011_expenses.sql).
The app never sends user_id — Postgres derives it from the token via auth.uid().
Every network or Supabase failure here becomes an ExpensesUnavailable; nothing above ever sees a
Postgrest/httpx exception.

Swappable for tests: app.extensions["expenses_repository"] holds the active repository.
"""
import logging
from contextlib import contextmanager

import httpx
from flask import current_app
from postgrest.exceptions import APIError

from app.blueprints.tools.expenses.errors import ExpensesUnavailable
from app.services.supabase_client import SupabaseNotConfigured, create_user_client

logger = logging.getLogger(__name__)

TABLE = "expenses"
COLUMNS = "id, amount, description, currency, spent_at, created_at, updated_at"


def get_repository():
    return current_app.extensions["expenses_repository"]


class SupabaseExpensesRepository:

    def list_month(self, access_token, year, month):
        """All expenses for the given year-month, newest spent_at first."""
        start = f"{year:04d}-{month:02d}-01"
        # Next month's first day as exclusive upper bound.
        if month == 12:
            end = f"{year + 1:04d}-01-01"
        else:
            end = f"{year:04d}-{month + 1:02d}-01"
        with self._errors("list_month"):
            response = (
                self._client(access_token)
                .table(TABLE)
                .select(COLUMNS)
                .gte("spent_at", start)
                .lt("spent_at", end)
                .order("spent_at", desc=True)
                .order("created_at", desc=True)
                .execute()
            )
        return response.data

    def insert_expense(self, access_token, amount, description, currency, spent_at, client_id=None):
        row = {"amount": str(amount), "description": description, "currency": currency, "spent_at": spent_at}
        if client_id:
            row["client_id"] = client_id
        with self._errors("insert_expense"):
            response = self._client(access_token).table(TABLE).insert(row).select(COLUMNS).execute()
        return response.data[0]

    def update_expense(self, access_token, expense_id, amount, description, currency, spent_at):
        with self._errors("update_expense"):
            response = (
                self._client(access_token)
                .table(TABLE)
                .update({"amount": str(amount), "description": description, "currency": currency, "spent_at": spent_at})
                .eq("id", expense_id)
                .select(COLUMNS)
                .execute()
            )
        return response.data[0] if response.data else None

    def delete_expense(self, access_token, expense_id):
        with self._errors("delete_expense"):
            response = (
                self._client(access_token).table(TABLE).delete().eq("id", expense_id).select("id").execute()
            )
        return bool(response.data)

    def import_expenses(self, access_token, expenses):
        """Insert guest expenses not yet saved. client_id uniqueness prevents duplicates on retry."""
        if not expenses:
            return []
        with self._errors("import_expenses"):
            response = (
                self._client(access_token)
                .table(TABLE)
                .upsert(expenses, on_conflict="user_id,client_id", ignore_duplicates=True)
                .select(COLUMNS)
                .execute()
            )
        return response.data

    def _client(self, access_token):
        return create_user_client(access_token)

    @contextmanager
    def _errors(self, action):
        try:
            yield
        except SupabaseNotConfigured:
            logger.error("Supabase is not configured: set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY")
            raise ExpensesUnavailable() from None
        except (APIError, httpx.HTTPError) as error:
            logger.warning("Supabase error during expenses.%s: %s", action, error)
            raise ExpensesUnavailable() from None
