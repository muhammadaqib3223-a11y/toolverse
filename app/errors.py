"""Friendly error pages. Flask already logs the full traceback of unhandled errors."""
import logging

from flask import flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_wtf.csrf import CSRFError

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("errors/500.html"), 500

    @app.errorhandler(CSRFError)
    def form_expired(error):
        # Usually a form left open after logging out in another tab, or blocked cookies.
        logger.warning("CSRF check failed on %s: %s", request.path, error.description)
        flash(_("This form expired. Please try again."), "error")
        can_reload = request.url_rule is not None and "GET" in request.url_rule.methods
        return redirect(request.full_path.rstrip("?") if can_reload else url_for("marketing.index"))
