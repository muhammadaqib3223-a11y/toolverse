"""Public marketing website: landing page, language switch, coming-soon pages."""
from flask import Blueprint

bp = Blueprint("marketing", __name__)

from app.blueprints.marketing import routes  # noqa: E402,F401  (registers the routes)
