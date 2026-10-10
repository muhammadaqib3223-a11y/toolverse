"""Supabase clients, built from the settings in .env.

A Supabase client remembers the user it is working for, so a NEW client is made for every
request and is never shared between two people. The HTTP connection pool underneath is shared,
so making a client is cheap and connections to Supabase are reused.
"""
import threading

import httpx
from flask import current_app
from supabase import Client, ClientOptions, create_client

_http_client = None
_http_client_lock = threading.Lock()


class SupabaseNotConfigured(RuntimeError):
    """SUPABASE_URL or SUPABASE_PUBLISHABLE_KEY is missing."""


def is_supabase_configured():
    config = current_app.config
    return bool(config["SUPABASE_URL"] and config["SUPABASE_PUBLISHABLE_KEY"])


def supabase_url():
    return current_app.config["SUPABASE_URL"]


def create_supabase_client() -> Client:
    """A fresh client that acts as an anonymous visitor (publishable key only)."""
    if not is_supabase_configured():
        raise SupabaseNotConfigured("Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in .env")

    options = ClientOptions(
        # Serverless: nothing may run after the response is sent, and nothing is kept between
        # requests. Tokens live in the user's cookie and are refreshed by app/blueprints/auth/session.py.
        auto_refresh_token=False,
        persist_session=False,
        # We run the PKCE steps for Google login ourselves (see auth/services.py), because the
        # code verifier must survive between two requests in the user's cookie.
        flow_type="implicit",
        httpx_client=_shared_http_client(),
    )
    return create_client(supabase_url(), current_app.config["SUPABASE_PUBLISHABLE_KEY"], options)


def _shared_http_client():
    global _http_client
    if _http_client is None:
        with _http_client_lock:
            if _http_client is None:
                _http_client = httpx.Client(
                    timeout=current_app.config["SUPABASE_TIMEOUT_SECONDS"],
                    follow_redirects=True,
                )
    return _http_client
