"""sitemap.xml and robots.txt. URLs are built from the current request, so no domain is hardcoded."""
from flask import Response, render_template, url_for

from app.blueprints.marketing import tools_catalog
from app.blueprints.seo import bp


def _public_urls():
    """Every page we want search engines to index."""
    urls = [
        url_for("marketing.index", _external=True),
        url_for("marketing.tools_index", _external=True),
    ]
    urls += [url_for("marketing.tool_detail", slug=tool.slug, _external=True) for tool in tools_catalog.TOOLS]
    return urls


@bp.get("/sitemap.xml")
def sitemap():
    body = render_template("seo/sitemap.xml", urls=_public_urls())
    return Response(body, mimetype="application/xml")


@bp.get("/robots.txt")
def robots():
    body = render_template("seo/robots.txt")
    return Response(body, mimetype="text/plain")
