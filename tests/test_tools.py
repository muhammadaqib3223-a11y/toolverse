import pytest
from flask import url_for

from app.blueprints.marketing import tools_catalog
from app.blueprints.marketing.tools_catalog import TOOLS, Status

SLUGS = [tool.slug for tool in TOOLS]


def test_tools_page_lists_every_tool(client):
    response = client.get("/tools")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    for slug in SLUGS:
        assert f'href="/tools/{slug}"' in html


def test_tools_page_has_a_tab_for_every_category(client):
    html = client.get("/tools").get_data(as_text=True)
    for category in tools_catalog.CATEGORIES:
        assert f'data-filter="{category.key}"' in html


def test_every_card_is_filterable_by_a_known_category(client):
    html = client.get("/tools").get_data(as_text=True)
    keys = {c.key for c in tools_catalog.CATEGORIES} - {tools_catalog.ALL}
    for key in keys:
        assert f'data-category="{key}"' in html


def test_coming_soon_badge_shown_for_tools_not_live(client):
    html = client.get("/tools").get_data(as_text=True)
    not_live = [tool for tool in TOOLS if not tool.is_live]
    assert html.count('class="status-badge"') == len(not_live)


@pytest.mark.parametrize("slug", SLUGS)
def test_tool_detail_page(client, app, slug):
    tool = tools_catalog.get_tool(slug)
    response = client.get(f"/tools/{slug}")
    html = response.get_data(as_text=True)
    assert response.status_code == 200

    hero = html.split('id="demo"', 1)[0]  # the bottom CTA also has a "Sign up free" button
    with app.test_request_context():
        try_url = url_for(tool.app_endpoint) if tool.is_live else url_for("auth.signup")
    assert f'href="{try_url}" class="btn-primary"' in hero


@pytest.mark.parametrize("tool", TOOLS, ids=SLUGS)
def test_tool_page_shows_all_sections(client, app, tool):
    html = client.get(f"/tools/{tool.slug}", headers={"Accept-Language": "en"}).get_data(as_text=True)

    with app.test_request_context():
        texts = [tool.description, *(f.title for f in tool.features), *(s.title for s in tool.steps),
                 *(q.question for q in tool.faqs), *tool.demo.tabs]
        for text in texts:
            assert str(text).replace("'", "&#39;") in html

    assert "data-demo" in html
    assert 'id="features"' in html and 'id="how-to-use"' in html and 'id="faq"' in html


@pytest.mark.parametrize("tool", TOOLS, ids=SLUGS)
def test_other_tools_section_lists_every_other_tool(client, tool):
    html = client.get(f"/tools/{tool.slug}").get_data(as_text=True)
    other_section = html.split('id="other-tools"', 1)[1]
    for other in TOOLS:
        link = f'href="/tools/{other.slug}"'
        if other.slug == tool.slug:
            assert link not in other_section
        else:
            assert link in other_section


def test_tool_page_in_urdu(client):
    html = client.get("/ur/tools/notes").get_data(as_text=True)
    assert 'dir="rtl"' in html
    assert "خصوصیات" in html and "استعمال کا طریقہ" in html


def test_landing_demo_shows_upload_limit(client):
    html = client.get("/", headers={"Accept-Language": "en"}).get_data(as_text=True)
    assert "PDF, up to 4 MB" in html
    assert "[X] MB" not in html


def test_unknown_tool_is_404(client):
    assert client.get("/tools/does-not-exist").status_code == 404


def test_tools_page_in_urdu(client):
    html = client.get("/ur/tools").get_data(as_text=True)
    assert 'dir="rtl"' in html
    assert "بنائیں۔ چیک کریں۔ بہتر کریں۔" in html


def test_navbar_tools_link_goes_to_tools_page(client):
    html = client.get("/", headers={"Accept-Language": "en"}).get_data(as_text=True)
    assert 'href="/tools" class="nav-link"' in html


def test_navbar_marks_tools_as_current_on_tools_pages(client):
    html = client.get("/tools/notes").get_data(as_text=True)
    assert 'class="nav-link is-active"' in html


def test_no_hardcoded_domain_in_preview(client):
    assert "toolverse.app" not in client.get("/").get_data(as_text=True)


# --- Catalog data checks: catch mistakes when a new tool is added. ---

def test_slugs_are_unique():
    assert len(SLUGS) == len(set(SLUGS))


@pytest.mark.parametrize("tool", TOOLS, ids=SLUGS)
def test_tool_data_is_complete(app, tool):
    category_keys = {c.key for c in tools_catalog.CATEGORIES} - {tools_catalog.ALL}
    assert tool.category in category_keys
    assert isinstance(tool.status, Status)
    assert len(tool.demo.tabs) == 3
    assert tool.demo.input_rows and tool.demo.checks and tool.demo.result_rows
    assert tool.features and tool.faqs
    assert len(tool.steps) == 3
    with app.test_request_context():
        assert str(tool.name) and str(tool.summary) and str(tool.description) and tool.icon


@pytest.mark.parametrize("tool", TOOLS, ids=SLUGS)
def test_every_icon_used_exists(app, tool):
    icons_source = (app.root_path + "/templates/partials/icons.html")
    with open(icons_source, encoding="utf-8") as f:
        source = f.read()
    for name in [tool.icon, *(feature.icon for feature in tool.features),
                 *(row.icon for row in tool.demo.input_rows + tool.demo.result_rows if row.icon)]:
        assert f'name == "{name}"' in source, f"missing icon: {name}"
