"""Business rules for notes: validation and limits. Routes call these functions and never see
the repository directly. The actual storage is app.extensions["notes_repository"] (repository.py),
so tests can swap in a fake one and never call Supabase (tests/fakes.py).
"""
import re

from app.blueprints.tools.notes.errors import NoteError, NoteNotFound
from app.blueprints.tools.notes.repository import get_repository

TITLE_MAX_LENGTH = 200
CONTENT_MAX_LENGTH = 20000
PAGE_SIZE = 50

# A search looks through at most this many of the caller's newest notes. Notes is a personal
# tool, not a huge archive, so this keeps search simple (plain Python matching, no database
# full-text setup or filter-string escaping) without limiting almost anyone in practice.
SEARCH_SCAN_LIMIT = 500

# Supabase ids are UUIDs; anything else can never match a row, so reject it before hitting the database.
_ID_RE = re.compile(r"^[0-9a-fA-F-]{8,36}$")


def list_notes(access_token, search=None, offset=0, limit=PAGE_SIZE):
    """(notes, has_more) for this page. `search` matches the title or the text."""
    repo = get_repository()
    if search:
        scanned = repo.list_notes(access_token, SEARCH_SCAN_LIMIT, 0)
        matches = [note for note in scanned if _matches(note, search)]
        has_more = offset + limit < len(matches)
        return matches[offset:offset + limit], has_more

    # Ask for one extra row to know whether there is a next page, without a separate count query.
    page = repo.list_notes(access_token, limit + 1, offset)
    has_more = len(page) > limit
    return page[:limit], has_more


def create_note(access_token, title, content, client_id=None):
    title, content = _validate(title, content)
    return get_repository().insert_note(access_token, title, content, client_id=client_id)


def update_note(access_token, note_id, title, content):
    _validate_id(note_id)
    title, content = _validate(title, content)
    note = get_repository().update_note(access_token, note_id, title, content)
    if note is None:
        raise NoteNotFound()
    return note


def delete_note(access_token, note_id):
    _validate_id(note_id)
    if not get_repository().delete_note(access_token, note_id):
        raise NoteNotFound()


def import_notes(access_token, guest_notes):
    """Move guest notes into the account. A note already moved (same client_id) is skipped by
    the database's unique constraint, so retrying after a dropped connection never duplicates it.
    A guest note that no longer fits the limits is skipped rather than failing the whole import.
    """
    rows = []
    for note in guest_notes if isinstance(guest_notes, list) else []:
        if not isinstance(note, dict):
            continue
        client_id = str(note.get("id") or "").strip()
        if not client_id:
            continue
        try:
            title, content = _validate(note.get("title", ""), note.get("content", ""))
        except NoteError:
            continue
        rows.append({"title": title, "content": content, "client_id": client_id})
    if not rows:
        return []
    return get_repository().import_notes(access_token, rows)


def _validate(title, content):
    title = (title or "").strip()
    content = content if isinstance(content, str) else ""
    if not title:
        raise NoteError("title_required")
    if len(title) > TITLE_MAX_LENGTH:
        raise NoteError("title_too_long")
    if len(content) > CONTENT_MAX_LENGTH:
        raise NoteError("content_too_long")
    return title, content


def _validate_id(note_id):
    if not note_id or not _ID_RE.match(note_id):
        raise NoteNotFound()


def _matches(note, search):
    needle = search.strip().lower()
    return needle in (note.get("title") or "").lower() or needle in (note.get("content") or "").lower()
