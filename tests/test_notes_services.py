"""Unit tests for the notes business rules (validation, limits, search) — no HTTP, no Supabase."""
import pytest

from app.blueprints.tools.notes import services
from app.blueprints.tools.notes.errors import NoteError, NoteNotFound, NotesUnavailable

TOKEN = "access-1"


@pytest.fixture
def ctx(app, notes_repository):
    with app.app_context():
        yield notes_repository


def test_create_note_returns_the_saved_note(ctx):
    note = services.create_note(TOKEN, "Shopping list", "Milk, eggs")
    assert note["title"] == "Shopping list"
    assert note["content"] == "Milk, eggs"
    assert note["id"]


def test_create_note_trims_the_title(ctx):
    note = services.create_note(TOKEN, "  Trimmed  ", "")
    assert note["title"] == "Trimmed"


def test_create_note_without_a_title_fails(ctx):
    with pytest.raises(NoteError) as excinfo:
        services.create_note(TOKEN, "   ", "text")
    assert excinfo.value.code == "title_required"


def test_create_note_title_too_long_fails(ctx):
    with pytest.raises(NoteError) as excinfo:
        services.create_note(TOKEN, "x" * 201, "")
    assert excinfo.value.code == "title_too_long"


def test_create_note_content_too_long_fails(ctx):
    with pytest.raises(NoteError) as excinfo:
        services.create_note(TOKEN, "Title", "x" * 20001)
    assert excinfo.value.code == "content_too_long"


def test_update_note_changes_title_and_content(ctx):
    note = services.create_note(TOKEN, "Old title", "Old text")
    updated = services.update_note(TOKEN, note["id"], "New title", "New text")
    assert updated["title"] == "New title"
    assert updated["content"] == "New text"


def test_update_missing_note_raises_not_found(ctx):
    with pytest.raises(NoteNotFound):
        services.update_note(TOKEN, "00000000-0000-0000-0000-000000000000", "Title", "")


def test_update_malformed_id_raises_not_found(ctx):
    with pytest.raises(NoteNotFound):
        services.update_note(TOKEN, "not-a-uuid", "Title", "")


def test_update_someone_elses_note_raises_not_found(ctx):
    note = services.create_note(TOKEN, "Mine", "")
    with pytest.raises(NoteNotFound):
        services.update_note("access-2", note["id"], "Stolen", "")


def test_delete_note_removes_it(ctx):
    note = services.create_note(TOKEN, "Delete me", "")
    services.delete_note(TOKEN, note["id"])
    notes, _ = services.list_notes(TOKEN)
    assert notes == []


def test_delete_missing_note_raises_not_found(ctx):
    with pytest.raises(NoteNotFound):
        services.delete_note(TOKEN, "00000000-0000-0000-0000-000000000000")


def test_list_notes_newest_first(ctx):
    first = services.create_note(TOKEN, "First", "")
    second = services.create_note(TOKEN, "Second", "")
    notes, has_more = services.list_notes(TOKEN)
    assert [n["id"] for n in notes] == [second["id"], first["id"]]
    assert has_more is False


def test_list_notes_paginates(ctx):
    for i in range(5):
        services.create_note(TOKEN, f"Note {i}", "")
    page, has_more = services.list_notes(TOKEN, offset=0, limit=2)
    assert len(page) == 2
    assert has_more is True
    page2, has_more2 = services.list_notes(TOKEN, offset=4, limit=2)
    assert len(page2) == 1
    assert has_more2 is False


def test_search_matches_title_or_content(ctx):
    services.create_note(TOKEN, "Meeting notes", "Discuss the budget")
    services.create_note(TOKEN, "Shopping", "Milk and eggs")
    notes, _ = services.list_notes(TOKEN, search="budget")
    assert len(notes) == 1
    assert notes[0]["title"] == "Meeting notes"


def test_search_is_case_insensitive(ctx):
    services.create_note(TOKEN, "Meeting Notes", "")
    notes, _ = services.list_notes(TOKEN, search="meeting")
    assert len(notes) == 1


def test_search_with_no_matches_returns_empty(ctx):
    services.create_note(TOKEN, "Meeting notes", "")
    notes, has_more = services.list_notes(TOKEN, search="nothing-like-this")
    assert notes == []
    assert has_more is False


def test_import_notes_creates_each_one(ctx):
    guest_notes = [
        {"id": "guest-1", "title": "First", "content": "a"},
        {"id": "guest-2", "title": "Second", "content": "b"},
    ]
    imported = services.import_notes(TOKEN, guest_notes)
    assert len(imported) == 2
    notes, _ = services.list_notes(TOKEN)
    assert len(notes) == 2


def test_import_notes_is_safe_to_retry(ctx):
    guest_notes = [{"id": "guest-1", "title": "First", "content": "a"}]
    services.import_notes(TOKEN, guest_notes)
    services.import_notes(TOKEN, guest_notes)  # retried, e.g. after a dropped connection
    notes, _ = services.list_notes(TOKEN)
    assert len(notes) == 1


def test_import_skips_a_note_without_a_title(ctx):
    guest_notes = [
        {"id": "guest-1", "title": "", "content": "no title"},
        {"id": "guest-2", "title": "Valid", "content": ""},
    ]
    imported = services.import_notes(TOKEN, guest_notes)
    assert len(imported) == 1
    assert imported[0]["title"] == "Valid"


def test_import_with_no_valid_notes_returns_empty_list(ctx):
    assert services.import_notes(TOKEN, [{"id": "guest-1", "title": "", "content": ""}]) == []
    assert services.import_notes(TOKEN, []) == []


def test_two_users_notes_never_mix(ctx):
    services.create_note("access-1", "User one's note", "")
    services.create_note("access-2", "User two's note", "")
    notes_one, _ = services.list_notes("access-1")
    notes_two, _ = services.list_notes("access-2")
    assert [n["title"] for n in notes_one] == ["User one's note"]
    assert [n["title"] for n in notes_two] == ["User two's note"]


def test_unavailable_repository_raises_notes_unavailable(app, notes_repository):
    notes_repository.unavailable = True
    with app.app_context():
        with pytest.raises(NotesUnavailable):
            services.list_notes(TOKEN)
