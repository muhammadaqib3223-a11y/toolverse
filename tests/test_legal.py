"""Privacy Policy (/privacy) and Terms of Service (/terms)."""
import html as html_lib
import re

import pytest

from app.blueprints.marketing import legal

CONTACT = "muhammadaqib3223@gmail.com"


def _html(response):
    return html_lib.unescape(response.get_data(as_text=True))


@pytest.mark.parametrize("path,title", [("/privacy", "Privacy Policy"), ("/terms", "Terms of Service")])
def test_legal_pages_render(client, path, title):
    response = client.get(path)
    html = _html(response)
    assert response.status_code == 200
    assert f">{title}</h1>" in html
    assert "Last updated: October 10, 2026" in html
    assert 'name="robots"' not in html  # these pages may appear in search results


@pytest.mark.parametrize("path", ["/ur/privacy", "/ur/terms"])
def test_legal_pages_in_urdu(client, path):
    html = _html(client.get(path))
    assert 'lang="ur" dir="rtl"' in html
    assert "آخری تبدیلی: 10 اکتوبر، 2026" in html
    assert f'hreflang="en" href="http://localhost{path[3:]}"' in html


def test_every_block_is_rendered(client, app):
    for page in legal.PAGES:
        html = _html(client.get("/" + page.endpoint.split(".")[1]))
        with app.test_request_context():
            for block in page.blocks:
                texts = [block.text] if block.text else [
                    cell for item in block.items for cell in (item if isinstance(item, tuple) else (item,))]
                for text in texts:
                    plain = str(text).replace("%(email)s", CONTACT).replace("%(cookie)s", "session")
                    assert re.sub(r"<[^>]+>", "", plain) in re.sub(r"<[^>]+>", "", html), plain


def test_contact_email_is_a_link_and_no_placeholder_is_left(client):
    for path in ["/privacy", "/terms", "/ur/privacy", "/ur/terms"]:
        html = _html(client.get(path))
        assert f'<a href="mailto:{CONTACT}" dir="ltr">{CONTACT}</a>' in html
        assert "%(" not in html


def test_privacy_tells_the_truth_about_what_the_code_does(client, app):
    html = _html(client.get("/privacy"))
    # Exactly the cookie we set, and how long it lasts.
    assert f'<code dir="ltr">{app.config["SESSION_COOKIE_NAME"]}</code>' in html
    assert app.config["PERMANENT_SESSION_LIFETIME"].days == 30 and "up to 30 days" in html
    # The Gemini free-tier warning is shown as a highlighted note.
    assert re.search(r'<p class="guide-note" role="note">We use the free version of Gemini', html)
    assert "A CV checked as a guest is never saved." in html
    assert "Send an email to" in html and "Delete my account" in html


def test_age_limit_is_18_on_both_pages(client):
    assert "only for people aged 18 or older" in _html(client.get("/privacy"))
    assert "at least 18 years old" in _html(client.get("/terms"))


def test_each_page_links_to_the_other(client):
    assert 'href="/terms" class="btn-secondary' in _html(client.get("/privacy"))
    assert 'href="/ur/privacy" class="btn-secondary' in _html(client.get("/ur/terms"))


def test_footer_and_signup_link_to_the_legal_pages(client, auth_service):
    home = _html(client.get("/"))
    assert 'href="/privacy"' in home and 'href="/terms"' in home
    signup = _html(client.get("/ur/signup"))
    assert 'href="/ur/privacy"' in signup and 'href="/ur/terms"' in signup
