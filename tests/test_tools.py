import pytest

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
def test_tool_detail_page(client, slug):
    response = client.get(f"/tools/{slug}")
    assert response.status_code == 200
    assert "/coming-soon/signup" in response.get_data(as_text=True)


def test_unknown_tool_is_404(client):
    assert client.get("/tools/does-not-exist").status_code == 404


def test_tools_page_in_urdu(client):
    html = client.get("/tools", headers={"Accept-Language": "ur"}).get_data(as_text=True)
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
    with app.test_request_context():
        assert str(tool.name) and str(tool.summary) and tool.icon
