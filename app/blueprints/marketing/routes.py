"""HTTP routes for the marketing website."""
from urllib.parse import urlparse

from flask import abort, redirect, render_template, request, url_for

from app.blueprints.marketing import bp, content, tools_catalog
from app.i18n import set_language


@bp.get("/")
def index():
    return render_template(
        "marketing/index.html",
        preview_tools=content.PREVIEW_TOOLS,
        steps=content.STEPS,
        free_points=content.FREE_POINTS,
        faqs=content.FAQS,
    )


@bp.get("/tools")
def tools_index():
    return render_template(
        "marketing/tools/index.html",
        categories=tools_catalog.CATEGORIES,
        featured_tools=tools_catalog.featured_tools(),
        grid_tools=tools_catalog.grid_tools(),
    )


@bp.get("/tools/<slug>")
def tool_detail(slug):
    tool = tools_catalog.get_tool(slug)
    if tool is None:
        abort(404)
    return render_template("marketing/tools/detail.html", tool=tool)


@bp.get("/coming-soon/<page>")
def coming_soon(page):
    info = content.COMING_SOON_PAGES.get(page)
    if info is None:
        abort(404)
    return render_template("marketing/coming_soon.html", page=info)


@bp.get("/lang/<code>")
def switch_language(code):
    if not set_language(code):
        abort(404)
    return redirect(_safe_return_url())


def _safe_return_url():
    """Go back to the page the user came from, but only if it is on our own site."""
    referrer = request.referrer
    if referrer and urlparse(referrer).netloc == request.host:
        return referrer
    return url_for("marketing.index")
