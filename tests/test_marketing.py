import pytest


def test_landing_page_renders_in_english(client):
    response = client.get("/", headers={"Accept-Language": "en"})
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'dir="ltr"' in html
    assert "Five tools. One login." in html
    assert '<span class="text-accent">work</span>' in html


def test_urdu_home_page_is_rtl(client):
    html = client.get("/ur").get_data(as_text=True)
    assert 'lang="ur" dir="rtl"' in html
    assert "پانچ ٹولز۔ ایک لاگ ان۔" in html


def test_root_is_english_even_for_urdu_browsers(client):
    html = client.get("/", headers={"Accept-Language": "ur"}).get_data(as_text=True)
    assert 'lang="en" dir="ltr"' in html


def test_unknown_language_prefix_is_404(client):
    assert client.get("/fr/tools").status_code == 404


@pytest.mark.parametrize("page", ["contact"])
def test_coming_soon_pages(client, page):
    response = client.get(f"/coming-soon/{page}")
    assert response.status_code == 200
    assert "Coming soon" in response.get_data(as_text=True)


@pytest.mark.parametrize("old,new", [
    ("/coming-soon/login", "/login"),
    ("/coming-soon/signup", "/signup"),
    ("/ur/coming-soon/signup", "/ur/signup"),
    ("/coming-soon/privacy", "/privacy"),
    ("/coming-soon/terms", "/terms"),
    ("/ur/coming-soon/privacy", "/ur/privacy"),
])
def test_old_coming_soon_links_redirect_to_the_real_pages(client, old, new):
    response = client.get(old)
    assert response.status_code == 301
    assert response.headers["Location"] == new


def test_sign_up_buttons_go_to_the_signup_page(client):
    html = client.get("/").get_data(as_text=True)
    assert 'href="/signup"' in html
    assert "/coming-soon/signup" not in html


def test_unknown_coming_soon_page_is_404(client):
    response = client.get("/coming-soon/nope")
    assert response.status_code == 404
    assert "Page not found." in response.get_data(as_text=True)


def test_static_files_are_served_from_public(client):
    response = client.get("/static/css/app.css")
    assert response.status_code == 200
    assert response.mimetype == "text/css"


def test_production_requires_secret_key(monkeypatch):
    from app import config

    monkeypatch.setattr(config.ProductionConfig, "SECRET_KEY", None)
    with pytest.raises(RuntimeError):
        config.get_config("production")
