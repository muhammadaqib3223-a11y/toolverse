"""Talks to Supabase for the `captions` history table (logged-in users only). Row Level Security
keeps every user's captions private (supabase/migrations/20261012_captions.sql). Daily tries are
counted by the shared AI limit system (app/services/ai_quota.py), not here.
Every network or Supabase failure here becomes a CaptionsUnavailable.

Swappable for tests: app.extensions["captions_repository"] holds the active repository.
"""
import logging
from contextlib import contextmanager

import httpx
from flask import current_app
from postgrest.exceptions import APIError

from app.blueprints.tools.captions.errors import CaptionsUnavailable
from app.services.supabase_client import SupabaseNotConfigured, create_user_client

logger = logging.getLogger(__name__)

TABLE = "captions"
COLUMNS = "id, topic, platform, captions, created_at"


def get_repository():
    return current_app.extensions["captions_repository"]


class SupabaseCaptionsRepository:

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
        return create_user_client(access_token)

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
