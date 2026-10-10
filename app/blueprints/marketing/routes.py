"""HTTP routes for the marketing website. Every page exists in English (/...) and Urdu (/ur/...)."""
from flask import abort, redirect, render_template, url_for

from app.blueprints.marketing import bp, content, legal, tools_catalog
from app.i18n import localized_route


@localized_route(bp, "/", methods=["GET"])
def index():
    return render_template(
        "marketing/index.html",
        preview_tools=content.PREVIEW_TOOLS,
        steps=content.STEPS,
        free_points=content.FREE_POINTS,
        faqs=content.FAQS,
    )


@localized_route(bp, "/tools", methods=["GET"])
def tools_index():
    return render_template(
        "marketing/tools/index.html",
        categories=tools_catalog.CATEGORIES,
        featured_tools=tools_catalog.featured_tools(),
        grid_tools=tools_catalog.grid_tools(),
    )


@localized_route(bp, "/tools/<slug>", methods=["GET"])
def tool_detail(slug):
    tool = tools_catalog.get_tool(slug)
    if tool is None:
        abort(404)
    return render_template(
        "marketing/tools/detail.html",
        tool=tool,
        other_tools=tools_catalog.other_tools(slug),
    )


@localized_route(bp, "/privacy", methods=["GET"])
def privacy():
    return render_template("marketing/legal.html", page=legal.PRIVACY, other_page=legal.TERMS)


@localized_route(bp, "/terms", methods=["GET"])
def terms():
    return render_template("marketing/legal.html", page=legal.TERMS, other_page=legal.PRIVACY)


# Pages that used to be "coming soon" and now exist; old links go to the real page.
_REAL_PAGES = {
    "login": "auth.login",
    "signup": "auth.signup",
    "privacy": "marketing.privacy",
    "terms": "marketing.terms",
}


@localized_route(bp, "/coming-soon/<page>", methods=["GET"])
def coming_soon(page):
    if page in _REAL_PAGES:
        return redirect(url_for(_REAL_PAGES[page]), code=301)
    info = content.COMING_SOON_PAGES.get(page)
    if info is None:
        abort(404)
    return render_template("marketing/coming_soon.html", page=info)
