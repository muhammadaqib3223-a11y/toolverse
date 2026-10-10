"""Accounts: signup, login, logout, password reset and Google login (Supabase Auth)."""
import logging

from flask import Blueprint, g, request

bp = Blueprint("auth", __name__)

from app.blueprints.auth import routes  # noqa: E402,F401  (registers the routes)

logger = logging.getLogger(__name__)


def init_auth(app):
    """Install the auth service and find the logged-in user before every request."""
    from app.blueprints.auth.services import SupabaseAuthService
    from app.blueprints.auth.session import load_current_user

    app.extensions["auth_service"] = SupabaseAuthService()

    if not (app.config["SUPABASE_URL"] and app.config["SUPABASE_PUBLISHABLE_KEY"]):
        logger.warning("SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY are not set: login will not work.")

    @app.before_request
    def find_current_user():
        if request.endpoint == "static":
            g.user = None
            return
        load_current_user()

    @app.context_processor
    def inject_current_user():
        return {"current_user": g.get("user")}
