"""The app area after login: dashboard home with the five tools in a sidebar."""
from flask import Blueprint

bp = Blueprint("dashboard", __name__)

from app.blueprints.dashboard import routes  # noqa: E402,F401  (registers the routes)
