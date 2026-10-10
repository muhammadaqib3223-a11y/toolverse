"""Notes: create, edit, delete and search.

A logged-in user's notes live in Supabase, private to them through Row Level Security.
A guest's notes stay in their own browser (see public/static/js/notes/) until they log in,
when the page offers to move them into the account.
"""
from flask import Blueprint

bp = Blueprint("notes", __name__)

from app.blueprints.tools.notes import routes  # noqa: E402,F401  (registers the routes)


def init_notes(app):
    """Install the real Supabase-backed repository (tests swap in a fake one)."""
    from app.blueprints.tools.notes.repository import SupabaseNotesRepository

    app.extensions["notes_repository"] = SupabaseNotesRepository()
