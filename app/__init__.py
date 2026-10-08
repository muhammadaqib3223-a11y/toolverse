"""Toolverse application factory."""
import logging
from datetime import datetime, timezone

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import get_config
from app.errors import register_error_handlers
from app.extensions import babel
from app.i18n import get_locale, register_i18n
from app.seo import faq_schema


def create_app(config_name=None):
    """Build and configure a Flask app. `config_name` overrides APP_ENV."""
    # Static files live in /public so Vercel's CDN serves them; Flask serves them locally.
    app = Flask(__name__, static_folder="../public/static")
    app.config.from_object(get_config(config_name))

    _configure_logging(app)

    if app.config["BEHIND_PROXY"]:
        # Render sits in front of the app; trust its forwarded host/scheme headers.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    babel.init_app(app, locale_selector=get_locale)
    register_i18n(app)
    _register_blueprints(app)
    register_error_handlers(app)
    _register_template_globals(app)

    return app


def _configure_logging(app):
    logging.basicConfig(
        level=app.config["LOG_LEVEL"],
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def _register_blueprints(app):
    from app.blueprints.marketing import bp as marketing_bp
    from app.blueprints.seo import bp as seo_bp

    app.register_blueprint(marketing_bp)
    app.register_blueprint(seo_bp)


def _register_template_globals(app):
    app.add_template_global(faq_schema)

    @app.context_processor
    def inject_globals():
        return {"current_year": datetime.now(timezone.utc).year}
