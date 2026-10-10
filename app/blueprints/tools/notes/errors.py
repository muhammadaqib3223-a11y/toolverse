"""Errors raised by the notes service. Each has a short `code`; messages.py turns it into
friendly, translated text. Routes never see a Supabase/Postgrest error directly."""


class NoteError(Exception):
    """Something the user can be told about, e.g. code="title_required"."""

    def __init__(self, code="unknown"):
        super().__init__(code)
        self.code = code


class NoteNotFound(NoteError):
    """No note with this id, or it isn't the caller's: the two look the same from outside."""

    def __init__(self):
        super().__init__("not_found")


class NotesUnavailable(NoteError):
    """The database could not be reached or is not configured. Nothing is wrong with the user's notes."""

    def __init__(self):
        super().__init__("unavailable")
