"""Errors raised by the CV Generator service. Each has a short `code` (and, for a problem with
one form field, the `field` it belongs to, e.g. "experience.1.description"); messages.py turns
the code into friendly, translated text."""


class CVError(Exception):
    def __init__(self, code="unknown", field=None):
        super().__init__(code)
        self.code = code
        self.field = field


class CVNotFound(CVError):
    def __init__(self):
        super().__init__("not_found")


class CVsUnavailable(CVError):
    """Supabase is down or not configured."""

    def __init__(self):
        super().__init__("unavailable")
