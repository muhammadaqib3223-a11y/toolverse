"""Safe "come back here after login" links (the ?next= parameter)."""
from urllib.parse import urlsplit

from flask import request, url_for


def safe_next_url(target):
    """`target` if it is a path on this site, otherwise None.

    Blocks open redirects: other domains, protocol-relative URLs (//evil.com),
    backslash tricks (browsers read a backslash like a slash) and hidden control characters.
    """
    if not target or not isinstance(target, str) or len(target) > 2000:
        return None
    if not target.startswith("/") or target.startswith("//") or "\\" in target:
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in target):
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return None
    return target


def next_url_from_request():
    """The safe ?next= of the current request, or None. Forms post back to the same URL, so it is kept."""
    return safe_next_url(request.args.get("next"))


def after_login_url(next_url=None):
    """Where to go once logged in: the page the user wanted, else the dashboard."""
    return safe_next_url(next_url) or url_for("dashboard.home")


def current_path():
    """The current page as a relative URL, for ?next=."""
    return request.full_path.rstrip("?")
