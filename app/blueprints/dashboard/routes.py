"""Dashboard pages. Every page exists in English (/dashboard) and Urdu (/ur/dashboard)."""
from flask import g, render_template

from app.blueprints.auth.decorators import login_required
from app.blueprints.dashboard import bp
from app.blueprints.marketing.tools_catalog import TOOLS
from app.i18n import localized_route


@localized_route(bp, "/dashboard", methods=["GET"])
@login_required
def home():
    return render_template("dashboard/home.html", user=g.user, tools=TOOLS)
