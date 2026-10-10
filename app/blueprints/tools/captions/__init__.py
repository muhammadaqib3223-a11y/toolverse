"""Caption Generator: a topic + Instagram/LinkedIn in, several AI-written captions out.

Guests get a few free tries a day (counted by IP in Supabase); logged-in users get more and a
saved history. The AI call goes through app/services/ai/, never a vendor SDK directly.
"""
from flask import Blueprint

bp = Blueprint("captions", __name__)

from app.blueprints.tools.captions import routes  # noqa: E402,F401


def init_captions(app):
    from app.blueprints.tools.captions.repository import SupabaseCaptionsRepository

    app.extensions["captions_repository"] = SupabaseCaptionsRepository()
