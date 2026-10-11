"""CV Generator: a step-by-step form (personal details, summary, experience, education, skills),
a choice of templates and a PDF download.

Part A (this code): the form lives in the browser (public/static/js/cv_generator/) for guests
and logged-in users alike; the server only turns it into a PDF and keeps nothing.
Saved CVs and AI writing help come in part B.
"""
from flask import Blueprint

bp = Blueprint("cv_generator", __name__)

from app.blueprints.tools.cv_generator import routes  # noqa: E402,F401  (registers the routes)
