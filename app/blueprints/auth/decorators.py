"""Decorators for views that depend on who is logged in.

- login_required: only for logged-in users (dashboard home). Guests go to the login page.
- login_optional: guests AND logged-in users (the tools, once guest mode is built).
  The view reads g.user: None for a guest, the AuthUser when logged in.

Both mark the response as private, because it shows a particular user's data.
"""
from functools import wraps

from flask import g, make_response, redirect, url_for

from app.blueprints.auth.redirects import after_login_url, current_path, next_url_from_request


def _private(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            return redirect(url_for("auth.login", next=current_path()))
        return _private(make_response(view(*args, **kwargs)))
    return wrapped


def login_optional(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        return _private(make_response(view(*args, **kwargs)))
    return wrapped


def logged_out_only(view):
    """Login / signup pages: someone already logged in goes straight to where they wanted."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is not None:
            return redirect(after_login_url(next_url_from_request()))
        return _private(make_response(view(*args, **kwargs)))
    return wrapped
