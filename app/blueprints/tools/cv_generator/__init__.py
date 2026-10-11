"""CV Generator: a step-by-step form (personal details, summary, experience, education, skills),
five templates with an accent colour, and a PDF download.

Guests keep their CVs in the browser (public/static/js/cv_generator/) and can download the PDF
without logging in; logged-in users' CVs are saved in Supabase (several per user), private to
them through Row Level Security.
"""
from flask import Blueprint

bp = Blueprint("cv_generator", __name__)

from app.blueprints.tools.cv_generator import routes  # noqa: E402,F401  (registers the routes)


def init_cv_generator(app):
    """Install the real Supabase-backed repository (tests swap in a fake one)."""
    from app.blueprints.tools.cv_generator.repository import SupabaseCVsRepository

    app.extensions["cvs_repository"] = SupabaseCVsRepository()
