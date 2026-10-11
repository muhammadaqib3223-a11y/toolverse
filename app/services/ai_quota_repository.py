"""Talks to the shared AI daily-tries functions in Supabase (supabase/migrations/20261014_ai_tries.sql).

The `ai_tries` table behind them can't be read or written directly. A guest's client has no
token, so the functions count them by `ip_hash`; a user's client carries their token, so they
count auth.uid(). Every network or Supabase failure here becomes a QuotaUnavailable.

Swappable for tests: app.extensions["ai_quota_repository"] holds the active repository
(tests/fakes.py's FakeAIQuotaRepository).
"""
import logging
from contextlib import contextmanager

import httpx
from flask import current_app
from postgrest.exceptions import APIError

from app.services.supabase_client import SupabaseNotConfigured, create_supabase_client, create_user_client

logger = logging.getLogger(__name__)


class QuotaUnavailable(Exception):
    """Supabase is down or not configured, so tries can't be counted (the AI call must not run)."""


def get_repository():
    return current_app.extensions["ai_quota_repository"]


class SupabaseAIQuotaRepository:
    """`access_token` is None for a guest."""

    def consume_try(self, access_token, tool, ip_hash, limit, site_limit):
        """{"status": "ok" | "limit" | "site_limit", "try_id": str | None, "used": int}"""
        params = {"p_tool": tool, "p_ip_hash": ip_hash, "p_limit": limit, "p_site_limit": site_limit}
        with self._errors("consume_try"):
            response = self._client(access_token).rpc("consume_ai_try", params).execute()
        return response.data

    def refund_try(self, access_token, try_id):
        with self._errors("refund_try"):
            self._client(access_token).rpc("refund_ai_try", {"p_try_id": try_id}).execute()

    def tries_used(self, access_token, tool, ip_hash):
        with self._errors("tries_used"):
            response = self._client(access_token).rpc(
                "ai_tries_used", {"p_tool": tool, "p_ip_hash": ip_hash}
            ).execute()
        return int(response.data or 0)

    def _client(self, access_token):
        if access_token:
            return create_user_client(access_token)
        return create_supabase_client()

    @contextmanager
    def _errors(self, action):
        try:
            yield
        except SupabaseNotConfigured:
            logger.error("Supabase is not configured: set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY")
            raise QuotaUnavailable() from None
        except (APIError, httpx.HTTPError) as error:
            logger.warning("Supabase error during ai_quota.%s: %s", action, error)
            raise QuotaUnavailable() from None
