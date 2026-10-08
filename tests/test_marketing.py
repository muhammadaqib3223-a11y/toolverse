import pytest


def test_landing_page_renders_in_english(client):
    response = client.get("/", headers={"Accept-Language": "en"})
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'dir="ltr"' in html
    assert "Five tools. One login." in html
    assert '<span class="text-accent">work</span>' in html


def test_switching_to_urdu_turns_page_rtl(client):
    response = client.get("/lang/ur", headers={"Referer": "http://localhost/"})
    assert response.status_code == 302

    html = client.get("/").get_data(as_text=True)
    assert 'lang="ur" dir="rtl"' in html
    assert "پانچ ٹولز۔ ایک لاگ ان۔" in html


def test_browser_language_is_used_when_nothing_chosen(client):
    html = client.get("/", headers={"Accept-Language": "ur"}).get_data(as_text=True)
    assert 'dir="rtl"' in html


def test_unknown_language_is_404(client):
    assert client.get("/lang/fr").status_code == 404


def test_language_switch_never_redirects_off_site(client):
    response = client.get("/lang/en", headers={"Referer": "https://evil.example/"})
    assert response.headers["Location"] == "/"


@pytest.mark.parametrize("page", ["login", "signup", "privacy", "terms", "contact"])
def test_coming_soon_pages(client, page):
    response = client.get(f"/coming-soon/{page}")
    assert response.status_code == 200
    assert "Coming soon" in response.get_data(as_text=True)


def test_unknown_coming_soon_page_is_404(client):
    response = client.get("/coming-soon/nope")
    assert response.status_code == 404
    assert "Page not found." in response.get_data(as_text=True)


def test_production_requires_secret_key(monkeypatch):
    from app import config

    monkeypatch.setattr(config.ProductionConfig, "SECRET_KEY", None)
    with pytest.raises(RuntimeError):
        config.get_config("production")
