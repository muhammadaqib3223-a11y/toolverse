"""Talks to the `cvs` table in Supabase, as the signed-in user named by `access_token`.

Postgres then sees that user through auth.uid(), so Row Level Security keeps everyone's CVs
private automatically (see supabase/migrations/20261015_cvs.sql). Every Supabase or network
failure here becomes a CVError; nothing above this file ever sees a Postgrest/httpx exception.

Swappable for tests: app.extensions["cvs_repository"] holds the active repository
(see get_repository(), and tests/fakes.py's FakeCVsRepository).
"""
import logging
from contextlib import contextmanager

import httpx
from flask import current_app
from postgrest.exceptions import APIError

from app.blueprints.tools.cv_generator.errors import CVError, CVsUnavailable
from app.services.supabase_client import SupabaseNotConfigured, create_user_client

logger = logging.getLogger(__name__)

TABLE = "cvs"
SUMMARY_COLUMNS = "id, title, template, accent, language, created_at, updated_at"
COLUMNS = SUMMARY_COLUMNS + ", data"

# Raised by the database trigger in 20261015_cvs.sql when a user already has the maximum.
LIMIT_ERROR = "cv_limit_reached"


def get_repository():
    return current_app.extensions["cvs_repository"]


class SupabaseCVsRepository:
    """The real repository. `access_token` is the caller's own Supabase access token."""

    def list_cvs(self, access_token, limit):
        """The user's CVs (without the form data), newest-updated first."""
        with self._errors("list_cvs"):
            response = (
                self._client(access_token)
                .table(TABLE)
                .select(SUMMARY_COLUMNS)
                .order("updated_at", desc=True)
                .limit(limit)
                .execute()
            )
        return response.data

    def get_cv(self, access_token, cv_id):
        """The full CV, or None if there is no such CV (not ours, or never existed)."""
        with self._errors("get_cv"):
            response = self._client(access_token).table(TABLE).select(COLUMNS).eq("id", cv_id).limit(1).execute()
        return response.data[0] if response.data else None

    def insert_cv(self, access_token, row):
        """`row`: title, data, template, accent, language (and optionally client_id)."""
        with self._errors("insert_cv"):
            response = self._client(access_token).table(TABLE).insert(row).select(COLUMNS).execute()
        return response.data[0]

    def update_cv(self, access_token, cv_id, row):
        """The updated CV, or None if there is no such CV."""
        with self._errors("update_cv"):
            response = (
                self._client(access_token).table(TABLE).update(row).eq("id", cv_id).select(COLUMNS).execute()
            )
        return response.data[0] if response.data else None

    def delete_cv(self, access_token, cv_id):
        """True if a CV was deleted."""
        with self._errors("delete_cv"):
            response = self._client(access_token).table(TABLE).delete().eq("id", cv_id).select("id").execute()
        return bool(response.data)

    def import_cvs(self, access_token, rows):
        """Insert guest CVs that aren't already saved. Each row needs a client_id (the guest CV's
        own id); one already saved is skipped by the database's unique constraint, so calling
        this twice with the same CVs never duplicates them. Returns the newly inserted CVs."""
        if not rows:
            return []
        with self._errors("import_cvs"):
            response = (
                self._client(access_token)
                .table(TABLE)
                .upsert(rows, on_conflict="user_id,client_id", ignore_duplicates=True)
                .select(SUMMARY_COLUMNS)
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
            raise CVsUnavailable() from None
        except APIError as error:
            if LIMIT_ERROR in str(error.message or ""):
                raise CVError("cv_limit") from None
            logger.warning("Supabase error during cvs.%s: %s", action, error)
            raise CVsUnavailable() from None
        except httpx.HTTPError as error:
            logger.warning("Network error during cvs.%s: %s", action, error)
            raise CVsUnavailable() from None
