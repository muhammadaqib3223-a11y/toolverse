"""Talks to Supabase for captions: the `captions` history table and the daily-tries functions.

History: Row Level Security keeps every user's captions private (supabase/migrations/20261012_captions.sql).
Tries: guests and users are counted by Postgres functions (20261013_captions_limits.sql). The
table behind them can't be read or written directly. A guest's client has no token, so the
function counts them by `ip_hash`; a user's client carries their token, so it counts auth.uid().
Every network or Supabase failure here becomes a CaptionsUnavailable.

Swappable for tests: app.extensions["captions_repository"] holds the active repository.
"""
import logging
from contextlib import contextmanager

import httpx
from flask import current_app
from postgrest.exceptions import APIError

from app.blueprints.tools.captions.errors import CaptionsUnavailable
from app.services.supabase_client import SupabaseNotConfigured, create_supabase_client, create_user_client

logger = logging.getLogger(__name__)

TABLE = "captions"
COLUMNS = "id, topic, platform, captions, created_at"


def get_repository():
    return current_app.extensions["captions_repository"]


class SupabaseCaptionsRepository:

    # --- daily tries (access_token is None for a guest) ---

    def consume_try(self, access_token, ip_hash, limit, site_limit):
        """{"status": "ok" | "limit" | "site_limit", "try_id": str | None, "used": int}"""
        params = {"p_ip_hash": ip_hash, "p_limit": limit, "p_site_limit": site_limit}
        with self._errors("consume_try"):
            response = self._client(access_token).rpc("consume_caption_try", params).execute()
        return response.data

    def refund_try(self, access_token, try_id):
        with self._errors("refund_try"):
            self._client(access_token).rpc("refund_caption_try", {"p_try_id": try_id}).execute()

    def tries_used(self, access_token, ip_hash):
        with self._errors("tries_used"):
            response = self._client(access_token).rpc("caption_tries_used", {"p_ip_hash": ip_hash}).execute()
        return int(response.data or 0)

    # --- history (logged-in users only) ---

    def insert_history(self, access_token, topic, platform, captions):
        row = {"topic": topic, "platform": platform, "captions": captions}
        with self._errors("insert_history"):
            response = self._client(access_token).table(TABLE).insert(row).select(COLUMNS).execute()
        return response.data[0]

    def list_history(self, access_token, limit):
        with self._errors("list_history"):
            response = (
                self._client(access_token)
                .table(TABLE)
                .select(COLUMNS)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
        return response.data

    def delete_history(self, access_token, caption_id):
        with self._errors("delete_history"):
            response = (
                self._client(access_token).table(TABLE).delete().eq("id", caption_id).select("id").execute()
            )
        return bool(response.data)

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
            raise CaptionsUnavailable() from None
        except (APIError, httpx.HTTPError) as error:
            logger.warning("Supabase error during captions.%s: %s", action, error)
            raise CaptionsUnavailable() from None
