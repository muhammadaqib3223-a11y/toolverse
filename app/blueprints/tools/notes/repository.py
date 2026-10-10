"""Talks to the `notes` table in Supabase, as the signed-in user named by `access_token`.

Postgres then sees that user through auth.uid(), so Row Level Security keeps everyone's notes
private automatically (see supabase/migrations/20261010_notes.sql). Every Supabase or network
failure here becomes a NoteError; nothing above this file ever sees a Postgrest/httpx exception.

Swappable for tests: app.extensions["notes_repository"] holds the active repository
(see get_repository(), and tests/fakes.py's FakeNotesRepository).
"""
import logging
from contextlib import contextmanager

import httpx
from flask import current_app
from postgrest.exceptions import APIError

from app.blueprints.tools.notes.errors import NotesUnavailable
from app.services.supabase_client import SupabaseNotConfigured, create_user_client

logger = logging.getLogger(__name__)

TABLE = "notes"
# user_id is never selected: the caller already knows it's their own notes, and it isn't
# something the page needs to show.
COLUMNS = "id, title, content, created_at, updated_at"


def get_repository():
    return current_app.extensions["notes_repository"]


class SupabaseNotesRepository:
    """The real repository. `access_token` is the caller's own Supabase access token."""

    def list_notes(self, access_token, limit, offset):
        """Up to `limit` notes, newest-updated first, starting at `offset`."""
        with self._errors("list_notes"):
            response = (
                self._client(access_token)
                .table(TABLE)
                .select(COLUMNS)
                .order("updated_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )
        return response.data

    def insert_note(self, access_token, title, content, client_id=None):
        row = {"title": title, "content": content}
        if client_id:
            row["client_id"] = client_id
        with self._errors("insert_note"):
            response = self._client(access_token).table(TABLE).insert(row).select(COLUMNS).execute()
        return response.data[0]

    def update_note(self, access_token, note_id, title, content):
        """The updated note, or None if there is no such note (not ours, or never existed)."""
        with self._errors("update_note"):
            response = (
                self._client(access_token)
                .table(TABLE)
                .update({"title": title, "content": content})
                .eq("id", note_id)
                .select(COLUMNS)
                .execute()
            )
        return response.data[0] if response.data else None

    def delete_note(self, access_token, note_id):
        """True if a note was deleted."""
        with self._errors("delete_note"):
            response = (
                self._client(access_token).table(TABLE).delete().eq("id", note_id).select("id").execute()
            )
        return bool(response.data)

    def import_notes(self, access_token, notes):
        """Insert guest notes that aren't already saved. Each `notes` item needs title, content
        and client_id (the guest note's own id); a client_id already saved is skipped by the
        database's unique constraint, so calling this twice with the same notes never duplicates them.
        Returns only the notes that were newly inserted.
        """
        if not notes:
            return []
        with self._errors("import_notes"):
            response = (
                self._client(access_token)
                .table(TABLE)
                .upsert(notes, on_conflict="user_id,client_id", ignore_duplicates=True)
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
            raise NotesUnavailable() from None
        except (APIError, httpx.HTTPError) as error:
            logger.warning("Supabase error during notes.%s: %s", action, error)
            raise NotesUnavailable() from None
