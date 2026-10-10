"""The dashboard (login required) with the five tools in the sidebar."""
import pytest
from flask import url_for

from app.blueprints.marketing.tools_catalog import TOOLS


def _html(response):
    return response.get_data(as_text=True)


@pytest.mark.parametrize("path,login_url", [
    ("/dashboard", "/login?next=/dashboard"),
    ("/ur/dashboard", "/ur/login?next=/ur/dashboard"),
])
def test_dashboard_needs_login(client, auth_service, path, login_url):
    response = client.get(path)
    assert response.status_code == 302
    assert response.headers["Location"] == login_url


def test_dashboard_welcomes_the_user(client, log_in):
    log_in(name="Sara Khan")
    response = client.get("/dashboard")
    html = _html(response)
    assert response.status_code == 200
    assert '<span class="text-accent">Sara Khan</span>' in html
    assert "sara@example.com" in html


def test_dashboard_uses_the_email_when_there_is_no_name(client, log_in):
    log_in(email="ali.raza@example.com", name="")
    assert '<span class="text-accent">ali.raza</span>' in _html(client.get("/dashboard"))


def test_dashboard_lists_tools_live_and_coming_soon(client, log_in, app):
    log_in()
    html = _html(client.get("/dashboard"))
    live = [tool for tool in TOOLS if tool.is_live]
    not_live = [tool for tool in TOOLS if not tool.is_live]

    for tool in not_live:
        assert f'href="/tools/{tool.slug}"' in html  # "Learn more" card link
    with app.test_request_context():
        for tool in live:
            assert f'href="{url_for(tool.app_endpoint)}"' in html  # "Open" card link + sidebar

    # Sidebar (laptop) + bottom menu (phone) both mark only the tools that aren't live yet.
    assert html.count('class="soon-badge"') == len(not_live)
    assert html.count('class="mobile-nav-item is-disabled"') == len(not_live)


def test_dashboard_has_a_logout_button_and_no_marketing_footer(client, log_in):
    log_in()
    html = _html(client.get("/dashboard"))
    assert html.count('action="/logout"') == 2  # sidebar + phone top bar
    assert "<footer" not in html


def test_dashboard_is_private(client, log_in):
    log_in()
    response = client.get("/dashboard")
    assert response.headers["Cache-Control"] == "private, no-store"
    assert '<meta name="robots" content="noindex">' in _html(response)


def test_urdu_dashboard(client, log_in):
    log_in()
    html = _html(client.get("/ur/dashboard"))
    assert 'lang="ur" dir="rtl"' in html
    assert 'action="/ur/logout"' in html
    assert 'hreflang="ur" href="/dashboard"' not in html
    assert '<a href="/dashboard"\n         lang="en"' in html  # language switch keeps the user on the dashboard


def test_guest_sidebar_has_no_link_to_login_only_dashboard_home(client, notes_repository):
    # /dashboard needs login, so linking guests there would bounce them to the login page.
    for path in ("/dashboard/notes", "/dashboard/expenses", "/ur/dashboard/notes"):
        html = client.get(path).get_data(as_text=True)
        assert 'href="/dashboard"' not in html
        assert 'href="/ur/dashboard"' not in html


def test_logged_in_sidebar_links_to_dashboard_home(client, log_in, notes_repository):
    log_in()
    html = client.get("/dashboard/notes").get_data(as_text=True)
    assert 'href="/dashboard" class="side-link' in html


def test_live_tool_detail_try_it_free_opens_the_tool_for_guests(client, notes_repository):
    html = client.get("/tools/notes").get_data(as_text=True)
    assert 'href="/dashboard/notes" class="btn-primary"' in html
    assert client.get("/dashboard/notes").status_code == 200
