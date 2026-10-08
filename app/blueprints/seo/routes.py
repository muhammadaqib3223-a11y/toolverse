"""sitemap.xml and robots.txt. URLs are built from the current request, so no domain is hardcoded."""
from flask import Response, current_app, render_template

from app.blueprints.marketing import tools_catalog
from app.blueprints.seo import bp
from app.i18n import localized_url


def _public_pages():
    """(endpoint, arguments) of every page we want search engines to index."""
    pages = [("marketing.index", {}), ("marketing.tools_index", {})]
    pages += [("marketing.tool_detail", {"slug": tool.slug}) for tool in tools_catalog.TOOLS]
    return pages


def _sitemap_entries():
    """One entry per page per language, each listing all its language versions."""
    languages = current_app.config["LANGUAGES"]
    entries = []
    for endpoint, args in _public_pages():
        alternates = {code: localized_url(endpoint, code, _external=True, **args) for code in languages}
        for code in languages:
            entries.append({"loc": alternates[code], "alternates": alternates})
    return entries


@bp.get("/sitemap.xml")
def sitemap():
    body = render_template(
        "seo/sitemap.xml",
        entries=_sitemap_entries(),
        default_language=current_app.config["BABEL_DEFAULT_LOCALE"],
    )
    return Response(body, mimetype="application/xml")


@bp.get("/robots.txt")
def robots():
    body = render_template("seo/robots.txt")
    return Response(body, mimetype="text/plain")
