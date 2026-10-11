"""Talks to the `cvs` table and the private `cv-photos` Storage bucket in Supabase, as the
signed-in user named by `access_token`.

Postgres then sees that user through auth.uid(), so Row Level Security keeps everyone's CVs
private automatically (see supabase/migrations/20261015_cvs.sql; photos: 20261016_cv_photos.sql,
where Storage policies only allow a user's own folder). Every Supabase or network
failure here becomes a CVError; nothing above this file ever sees a Postgrest/httpx exception.

Swappable for tests: app.extensions["cvs_repository"] holds the active repository
(see get_repository(), and tests/fakes.py's FakeCVsRepository).
"""
import logging
from contextlib import contextmanager

import httpx
from flask import current_app
from postgrest.exceptions import APIError
from storage3.exceptions import StorageApiError, StorageException

from app.blueprints.tools.cv_generator.errors import CVError, CVsUnavailable
from app.services.supabase_client import SupabaseNotConfigured, create_user_client, create_user_storage

logger = logging.getLogger(__name__)

TABLE = "cvs"
SUMMARY_COLUMNS = "id, title, template, accent, language, photo_path, created_at, updated_at"
PHOTO_BUCKET = "cv-photos"
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
                .select(SUMMARY_COLUMNS + ", client_id")
                .execute()
            )
        return response.data

    def set_photo_path(self, access_token, cv_id, photo_path):
        """Remember (or forget, with None) the CV's photo. The updated CV, or None if not found."""
        return self.update_cv(access_token, cv_id, {"photo_path": photo_path})

    def upload_photo(self, access_token, path, jpeg_bytes):
        with self._errors("upload_photo"):
            create_user_storage(access_token).from_(PHOTO_BUCKET).upload(
                path, jpeg_bytes, {"content-type": "image/jpeg", "upsert": "true", "cache-control": "0"}
            )

    def download_photo(self, access_token, path):
        """The JPEG bytes, or None if the file is not there."""
        with self._errors("download_photo"):
            try:
                return create_user_storage(access_token).from_(PHOTO_BUCKET).download(path)
            except StorageApiError as error:
                if str(error.status) in ("400", "404") and "not found" in str(error.message).lower():
                    return None
                raise

    def delete_photo(self, access_token, path):
        with self._errors("delete_photo"):
            create_user_storage(access_token).from_(PHOTO_BUCKET).remove([path])

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
        except StorageException as error:
            logger.warning("Supabase Storage error during cvs.%s: %s", action, error)
            raise CVsUnavailable() from None
        except httpx.HTTPError as error:
            logger.warning("Network error during cvs.%s: %s", action, error)
            raise CVsUnavailable() from None
