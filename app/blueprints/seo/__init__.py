"""Files for search engines: sitemap.xml and robots.txt."""
from flask import Blueprint

bp = Blueprint("seo", __name__)

from app.blueprints.seo import routes  # noqa: E402,F401  (registers the routes)
