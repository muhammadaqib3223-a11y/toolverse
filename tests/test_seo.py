import json
import re

import pytest

from app.blueprints.marketing.content import FAQS as LANDING_FAQS
from app.blueprints.marketing.tools_catalog import TOOLS

SLUGS = [tool.slug for tool in TOOLS]
PAGES = ["/", "/tools", *(f"/tools/{slug}" for slug in SLUGS)]


def _html(client, path, lang="en"):
    if lang != "en":
        path = f"/{lang}" + ("" if path == "/" else path)
    return client.get(path).get_data(as_text=True)


def _json_ld(html):
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    return [json.loads(block) for block in blocks]


# --- Titles and meta descriptions ---

def test_every_public_page_has_its_own_title_and_description(client):
    titles, descriptions = set(), set()
    for path in PAGES:
        html = _html(client, path)
        title = re.search(r"<title>(.*?)</title>", html, re.S).group(1).strip()
        description = re.search(r'<meta name="description" content="(.*?)">', html, re.S).group(1).strip()
        assert title and description, path
        titles.add(title)
        descriptions.add(description)
    assert len(titles) == len(PAGES)
    assert len(descriptions) == len(PAGES)


def test_canonical_link_uses_the_request_host(client):
    html = client.get("/tools/notes", base_url="https://example.test").get_data(as_text=True)
    assert '<link rel="canonical" href="https://example.test/tools/notes">' in html


@pytest.mark.parametrize("path", ["/coming-soon/privacy", "/does-not-exist"])
def test_placeholder_and_error_pages_are_noindex(client, path):
    assert '<meta name="robots" content="noindex">' in _html(client, path)


# --- Article ---

@pytest.mark.parametrize("tool", TOOLS, ids=SLUGS)
def test_article_is_long_enough_and_rendered(client, app, tool):
    with app.test_request_context():
        words = sum(len(str(block.text).split()) for block in tool.article)
        headings = [str(b.text) for b in tool.article if b.kind in ("h2", "h3")]
    assert 600 <= words <= 900
    assert any(b.kind == "h2" for b in tool.article) and any(b.kind == "h3" for b in tool.article)

    guide = _html(client, f"/tools/{tool.slug}").split('id="guide"', 1)[1].split("</article>", 1)[0]
    for heading in headings:
        assert heading.replace("'", "&#39;") in guide


def test_article_comes_after_features(client):
    html = _html(client, "/tools/notes")
    assert html.index('id="features"') < html.index('id="guide"') < html.index('id="how-to-use"')


def test_article_in_urdu(client):
    assert "نوٹس ٹول کیا ہے؟" in _html(client, "/tools/notes", lang="ur")


# --- FAQ ---

@pytest.mark.parametrize("tool", TOOLS, ids=SLUGS)
def test_tool_faq_has_six_to_eight_questions(tool):
    assert 6 <= len(tool.faqs) <= 8


@pytest.mark.parametrize("path", ["/", "/tools/cv-checker"])
def test_faq_is_an_accessible_accordion(client, path):
    html = _html(client, path)
    count = html.count("data-faq-trigger")
    assert count > 0
    assert html.count('aria-expanded="false"') >= count
    for n in range(1, count + 1):
        assert f'aria-controls="faq-a-{n}"' in html and f'id="faq-a-{n}"' in html
    assert "js/faq.js" in html


@pytest.mark.parametrize("path,faqs", [("/", LANDING_FAQS), *((f"/tools/{t.slug}", t.faqs) for t in TOOLS)])
def test_faq_page_schema_matches_the_visible_questions(client, app, path, faqs):
    schemas = [s for s in _json_ld(_html(client, path)) if s.get("@type") == "FAQPage"]
    assert len(schemas) == 1
    with app.test_request_context():
        expected = [str(f.question) for f in faqs]
    assert [q["name"] for q in schemas[0]["mainEntity"]] == expected
    assert all(q["acceptedAnswer"]["text"] for q in schemas[0]["mainEntity"])


def test_faq_schema_follows_the_language(client):
    schema = _json_ld(_html(client, "/tools/notes", lang="ur"))[0]
    assert schema["mainEntity"][0]["name"] == "میرے نوٹس کون دیکھ سکتا ہے؟"


def test_cv_checker_privacy_answer(client):
    html = _html(client, "/tools/cv-checker")
    assert "As a guest, your file is only checked and not saved." in html


# --- sitemap.xml and robots.txt ---

def _urdu(path):
    return "/ur" + ("" if path == "/" else path)


def test_sitemap_lists_both_languages_on_the_request_host(client):
    response = client.get("/sitemap.xml", base_url="https://example.test")
    xml = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.mimetype == "application/xml"
    assert xml.startswith("<?xml")
    for path in PAGES:
        en, ur = f"https://example.test{path}", f"https://example.test{_urdu(path)}"
        assert f"<loc>{en}</loc>" in xml
        assert f"<loc>{ur}</loc>" in xml
        assert f'<xhtml:link rel="alternate" hreflang="ur" href="{ur}"/>' in xml
        assert f'<xhtml:link rel="alternate" hreflang="x-default" href="{en}"/>' in xml
    assert xml.count("<url>") == 2 * len(PAGES)
    assert "coming-soon" not in xml


def test_robots_points_to_the_sitemap(client):
    response = client.get("/robots.txt", base_url="https://example.test")
    text = response.get_data(as_text=True)

    assert response.mimetype == "text/plain"
    assert "Sitemap: https://example.test/sitemap.xml" in text
