"""Toolverse application factory."""
import logging
from datetime import datetime, timezone

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import get_config
from app.errors import register_error_handlers
from app.extensions import babel, csrf
from app.i18n import get_locale, register_i18n
from app.seo import faq_schema


def create_app(config_name=None):
    """Build and configure a Flask app. `config_name` overrides APP_ENV."""
    # Static files live in /public so Vercel's CDN serves them; Flask serves them locally.
    app = Flask(__name__, static_folder="../public/static")
    app.config.from_object(get_config(config_name))

    _configure_logging(app)

    if app.config["BEHIND_PROXY"]:
        # Vercel sits in front of the app; trust its forwarded host/scheme/client-IP headers.
        # x_for=1 takes the LAST X-Forwarded-For entry, the one Vercel itself writes (Vercel
        # overwrites the header, so a visitor can't fake their IP; see app/services/client_ip.py).
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    babel.init_app(app, locale_selector=get_locale)
    csrf.init_app(app)
    register_i18n(app)
    _register_blueprints(app)
    _init_auth(app)
    _init_tools(app)
    register_error_handlers(app)
    _register_template_globals(app)

    return app


def _configure_logging(app):
    logging.basicConfig(
        level=app.config["LOG_LEVEL"],
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def _register_blueprints(app):
    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.dashboard import bp as dashboard_bp
    from app.blueprints.tools.captions import bp as captions_bp
    from app.blueprints.marketing import bp as marketing_bp
    from app.blueprints.seo import bp as seo_bp
    from app.blueprints.tools.expenses import bp as expenses_bp
    from app.blueprints.tools.notes import bp as notes_bp

    app.register_blueprint(marketing_bp)
    app.register_blueprint(seo_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(captions_bp)


def _init_auth(app):
    from app.blueprints.auth import init_auth

    init_auth(app)


def _init_tools(app):
    from app.blueprints.tools.captions import init_captions
    from app.blueprints.tools.expenses import init_expenses
    from app.services.ai import init_ai

    init_ai(app)
    from app.blueprints.tools.notes import init_notes

    init_notes(app)
    init_expenses(app)
    init_captions(app)


def _register_template_globals(app):
    from app.blueprints.marketing.tools_catalog import TOOLS

    app.add_template_global(faq_schema)

    @app.context_processor
    def inject_globals():
        return {"current_year": datetime.now(timezone.utc).year}

    # The tools shown in the dashboard sidebar / bottom menu. App-level (not a blueprint
    # context processor) because the sidebar is shared by the dashboard AND every tool's own
    # blueprint (Notes, then the rest), and a blueprint's context processor only runs for that
    # blueprint's own views.
    @app.context_processor
    def inject_nav_tools():
        return {"nav_tools": TOOLS}
