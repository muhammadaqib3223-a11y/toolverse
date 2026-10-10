"""Friendly, translated text for each notes error code (see errors.py and services.py)."""
from flask_babel import lazy_gettext as _l

ERROR_MESSAGES = {
    "login_required": _l("Please log in to use this."),
    "not_found": _l("That note no longer exists."),
    "title_required": _l("Please add a title."),
    "title_too_long": _l("The title is too long (200 characters max)."),
    "content_too_long": _l("The note is too long (20,000 characters max)."),
    "unavailable": _l("Notes aren't available right now. Please try again in a moment."),
    "unknown": _l("Something went wrong. Please try again."),
}


def error_message(error):
    """Text to show the user for a NoteError."""
    return ERROR_MESSAGES.get(error.code, ERROR_MESSAGES["unknown"])
