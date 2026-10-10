"""Errors raised by the captions service. Each has a short `code`; messages.py turns it into
friendly, translated text. Routes never see a Supabase or AI vendor error directly."""


class CaptionError(Exception):
    def __init__(self, code="unknown"):
        super().__init__(code)
        self.code = code


class CaptionNotFound(CaptionError):
    def __init__(self):
        super().__init__("not_found")


class CaptionsUnavailable(CaptionError):
    """Supabase is down or not configured."""

    def __init__(self):
        super().__init__("unavailable")
