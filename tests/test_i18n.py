import re

import pytest

HOST = "https://example.test"


def _get(client, path):
    return client.get(path, base_url=HOST).get_data(as_text=True)


@pytest.mark.parametrize("en,ur", [
    ("/", "/ur"),
    ("/tools", "/ur/tools"),
    ("/tools/cv-checker", "/ur/tools/cv-checker"),
    ("/coming-soon/privacy", "/ur/coming-soon/privacy"),
    ("/login", "/ur/login"),
    ("/signup", "/ur/signup"),
    ("/forgot-password", "/ur/forgot-password"),
])
def test_every_page_exists_in_both_languages(client, en, ur):
    en_html, ur_html = _get(client, en), _get(client, ur)
    assert 'lang="en" dir="ltr"' in en_html
    assert 'lang="ur" dir="rtl"' in ur_html


def test_links_on_an_urdu_page_stay_in_urdu(client):
    html = _get(client, "/ur/tools")
    hrefs = re.findall(r'href="(/[^"]*)"', html)
    page_links = [h for h in hrefs if not h.startswith("/static/") and h != "/"]
    # Every internal page link is under /ur, except the switch back to English
    # (shown twice: desktop navbar and mobile menu).
    english_links = {h for h in page_links if not h.startswith("/ur")}
    assert english_links == {"/tools"}
    assert 'href="/ur/tools/cv-checker"' in html


def test_language_switch_points_to_the_same_page_in_the_other_language(client):
    en_html = _get(client, "/tools/notes")
    assert re.search(r'<a href="/ur/tools/notes"\s+lang="ur" hreflang="ur"', en_html)

    ur_html = _get(client, "/ur/tools/notes")
    assert re.search(r'<a href="/tools/notes"\s+lang="en" hreflang="en"', ur_html)


@pytest.mark.parametrize("path", ["/tools/notes", "/ur/tools/notes"])
def test_hreflang_tags_on_every_page(client, path):
    html = _get(client, path)
    assert f'<link rel="alternate" hreflang="en" href="{HOST}/tools/notes">' in html
    assert f'<link rel="alternate" hreflang="ur" href="{HOST}/ur/tools/notes">' in html
    assert f'<link rel="alternate" hreflang="x-default" href="{HOST}/tools/notes">' in html


def test_canonical_points_to_the_page_in_its_own_language(client):
    html = _get(client, "/ur/tools/notes")
    assert f'<link rel="canonical" href="{HOST}/ur/tools/notes">' in html


def test_home_page_hreflang(client):
    html = _get(client, "/ur")
    assert f'hreflang="en" href="{HOST}/"' in html
    assert f'hreflang="ur" href="{HOST}/ur"' in html


def test_urdu_404_page_is_in_urdu(client):
    response = client.get("/ur/does-not-exist")
    html = response.get_data(as_text=True)
    assert response.status_code == 404
    assert 'dir="rtl"' in html
    assert "صفحہ نہیں ملا۔" in html
    assert 'hreflang="x-default"' not in html


def test_no_hardcoded_domain(client):
    for path in ["/", "/ur/tools/cv-checker", "/sitemap.xml"]:
        assert "toolverse.app" not in _get(client, path)
