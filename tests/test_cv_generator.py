"""CV Generator: the page, the PDF API (guests included), form checks and the PDF itself.
PDF text is read back with pypdf to prove it is real, selectable text (for ATS and our CV Checker)."""
import io
import pathlib

import pytest
from pypdf import PdfReader

from app.blueprints.tools.cv_generator import services
from app.blueprints.tools.cv_generator.errors import CVError
from app.services import pdf_builder

URDU_NAME = "محمد عاقب"
URDU_HEADLINE = "سافٹ ویئر انجینئر"


def _cv(**overrides):
    cv = {
        "personal": {
            "full_name": "Sara Khan",
            "headline": "Junior Data Analyst",
            "email": "sara@example.com",
            "phone": "+92 300 1234567",
            "location": "Lahore, Pakistan",
            "website": "linkedin.com/in/sarakhan",
        },
        "summary": "Data analyst who turns messy spreadsheets into clear dashboards.",
        "experience": [{
            "job_title": "Junior Data Analyst",
            "company": "Daraz",
            "location": "Lahore",
            "start": "Jan 2024",
            "current": True,
            "description": "- Built weekly sales dashboards\n- Cut report time from 2 days to 3 hours",
        }],
        "education": [{"degree": "BS Computer Science", "school": "FAST NUCES", "start": "2019", "end": "2023"}],
        "skills": ["Python", "SQL", "Power BI"],
    }
    cv.update(overrides)
    return cv


def _post(client, cv=None, template="classic", language="en", url="/api/cv-generator/pdf"):
    return client.post(url, json={"cv": cv if cv is not None else _cv(), "template": template, "language": language})


def _pdf_text(data):
    reader = PdfReader(io.BytesIO(data))
    text = "\n".join(page.extract_text() for page in reader.pages)
    # Shaped Urdu adds zero-width spaces for its extra glyphs (see pdf_builder); readers drop them.
    return text.replace(pdf_builder.INVISIBLE_GLYPH_TEXT, "")


# ── Page ────────────────────────────────────────────────────────────────────

def test_guest_can_open_cv_generator_page(client):
    response = client.get("/dashboard/cv-generator", follow_redirects=False)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "data-cv-app" in html
    assert 'data-api-pdf="/api/cv-generator/pdf"' in html


def test_urdu_page_is_rtl_and_defaults_to_urdu_cv(client):
    html = client.get("/ur/dashboard/cv-generator").get_data(as_text=True)
    assert 'dir="rtl"' in html
    assert 'data-default-language="ur"' in html
    assert 'data-api-pdf="/ur/api/cv-generator/pdf"' in html


def test_sidebar_links_to_cv_generator(client, log_in):
    log_in()
    html = client.get("/dashboard").get_data(as_text=True)
    assert 'href="/dashboard/cv-generator"' in html


def test_tool_page_try_button_opens_the_tool(client):
    html = client.get("/tools/cv-generator").get_data(as_text=True)
    assert 'href="/dashboard/cv-generator"' in html


def test_compiled_css_has_the_cv_classes(app):
    css = (pathlib.Path(app.static_folder) / "css" / "app.css").read_text(encoding="utf-8")
    for selector in (".cv-layout", ".cv-step", ".cv-entry", ".cv-skill", ".cv-template", ".cv-preview",
                     ".cv-swatch", ".cv-thumb-a", ".cv-ats-badge"):
        assert selector in css


def test_pdf_fonts_are_inside_the_app_package():
    # Vercel ships the app/ folder with the function (like templates and translations), so the
    # fonts must live there, not in public/ (which only the CDN serves).
    app_dir = pathlib.Path(pdf_builder.__file__).resolve().parent.parent
    for styles in pdf_builder.FONT_FILES.values():
        for file_name in styles.values():
            path = pdf_builder.FONTS_DIR / file_name
            assert path.is_file(), path
            assert app_dir in path.parents


# ── PDF download ────────────────────────────────────────────────────────────

def test_guest_gets_a_pdf_without_logging_in(client):
    response = _post(client)
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")
    assert 'attachment; filename="Sara_Khan_CV.pdf"' in response.headers["Content-Disposition"]
    assert response.headers["Cache-Control"] == "private, no-store"


def test_logged_in_user_gets_a_pdf_too(client, log_in):
    log_in()
    assert _post(client).status_code == 200


@pytest.mark.parametrize("template", services.TEMPLATES)
def test_every_template_makes_a_pdf_with_selectable_text(client, template):
    response = _post(client, template=template)
    assert response.status_code == 200
    text = _pdf_text(response.data)
    for expected in ("Sara Khan", "Junior Data Analyst", "sara@example.com", "+92 300 1234567",
                     "Daraz", "Built weekly sales dashboards", "BS Computer Science", "Python", "Power BI",
                     "EXPERIENCE", "EDUCATION", "SKILLS", "Present"):
        assert expected in text, (template, expected)


@pytest.mark.parametrize("template", services.TEMPLATES)
def test_urdu_text_is_selectable_in_the_pdf(client, template):
    cv = _cv(personal={"full_name": URDU_NAME, "headline": URDU_HEADLINE, "email": "aqib@example.com"})
    response = _post(client, cv=cv, template=template, language="ur")
    assert response.status_code == 200
    text = _pdf_text(response.data)
    assert URDU_NAME in text
    assert URDU_HEADLINE in text
    assert "تجربہ" in text  # "Experience" heading in Urdu
    assert "aqib@example.com" in text


def test_urdu_name_gets_an_ascii_fallback_filename(client):
    response = _post(client, cv=_cv(personal={"full_name": URDU_NAME}))
    disposition = response.headers["Content-Disposition"]
    assert 'filename="CV.pdf"' in disposition
    assert "filename*=UTF-8''" in disposition


def test_long_cv_flows_onto_more_pages(client):
    job = {"job_title": "Analyst", "company": "Company", "description": "\n".join(["- " + "Did useful work " * 8] * 6)}
    response = _post(client, cv=_cv(experience=[job] * services.MAX_EXPERIENCE), template="modern")
    assert response.status_code == 200
    assert len(PdfReader(io.BytesIO(response.data)).pages) > 1


def test_modern_template_moves_many_skills_out_of_the_side_column(client):
    skills = [f"Skill number {i} " + "x" * 40 for i in range(services.MAX_SKILLS)]
    response = _post(client, cv=_cv(skills=skills), template="modern")
    assert response.status_code == 200
    text = _pdf_text(response.data)
    assert "Skill number 39" in text


def test_urdu_api_answers_in_urdu(client):
    response = _post(client, cv=_cv(personal={"full_name": ""}), url="/ur/api/cv-generator/pdf")
    assert response.status_code == 400
    assert response.get_json()["message"] == "براہِ کرم اپنا پورا نام لکھیں۔"


# ── Form checks ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cv, code, field", [
    (_cv(personal={"full_name": "  "}), "name_required", "personal.full_name"),
    (_cv(personal={"full_name": "Sara", "email": "not-an-email"}), "email_invalid", "personal.email"),
    (_cv(personal={"full_name": "Sara", "website": "javascript:alert(1)"}), "website_invalid", "personal.website"),
    (_cv(personal={"full_name": "S" * 101}), "too_long", "personal.full_name"),
    (_cv(experience=[{"job_title": "A"}, {"description": "x" * 2001}]), "too_long", "experience.1.description"),
    (_cv(skills=["s%d" % i for i in range(services.MAX_SKILLS + 1)]), "too_many_skills", "skills"),
    (_cv(experience=[{"job_title": "A"}] * (services.MAX_EXPERIENCE + 1)), "too_many_experience", "experience"),
    (_cv(personal="Sara"), "invalid_data", None),
    (_cv(skills=[1, 2]), "invalid_data", "skills"),
])
def test_bad_form_data_gives_a_clear_error(client, cv, code, field):
    response = _post(client, cv=cv)
    assert response.status_code == 400
    body = response.get_json()
    assert body["code"] == code
    assert body["field"] == field
    assert body["message"]


def test_unknown_template_or_language_is_rejected(client):
    assert _post(client, template="fancy").get_json()["code"] == "template_invalid"
    assert _post(client, language="fr").get_json()["code"] == "language_invalid"


def test_non_json_body_is_rejected(client):
    response = client.post("/api/cv-generator/pdf", data="hello", content_type="text/plain")
    assert response.status_code == 400
    assert response.get_json()["code"] == "invalid_data"


def test_oversized_request_is_rejected(client, app):
    big = "x" * (app.config["CV_MAX_REQUEST_BYTES"] + 1)
    response = _post(client, cv=_cv(summary=big))
    assert response.status_code == 413
    assert response.get_json()["code"] == "too_large"


def test_pdf_failure_gives_a_friendly_error(client, monkeypatch):
    def broken(*args, **kwargs):
        raise pdf_builder.PdfBuildError("output_failed")
    monkeypatch.setattr(services, "render_cv", broken)
    response = _post(client)
    assert response.status_code == 500
    assert response.get_json()["code"] == "pdf_failed"


def test_pdf_needs_csrf_token(client, app):
    app.config["WTF_CSRF_ENABLED"] = True
    assert _post(client).status_code == 400


# ── Cleaning rules ──────────────────────────────────────────────────────────

def test_parse_cv_cleans_the_data():
    cv = services.parse_cv(_cv(
        personal={"full_name": "  Sara \t Khan\x00 ", "headline": "Line one\nline two"},
        summary="First line\r\n\n\n\n\nSecond line   ",
        experience=[{}, {"job_title": "  "}, {"company": "Daraz", "current": "yes"}],
        education=[{"school": "FAST"}],
        skills=["Python", " python ", "", "SQL"],
    ))
    assert cv.personal.full_name == "Sara Khan"
    assert cv.personal.headline == "Line one line two"
    assert cv.summary == "First line\n\nSecond line"
    assert len(cv.experience) == 1
    assert cv.experience[0].company == "Daraz"
    assert cv.experience[0].current is False  # only a real true counts
    assert cv.skills == ("Python", "SQL")


def test_parse_cv_needs_a_dict():
    with pytest.raises(CVError) as error:
        services.parse_cv(["not", "a", "cv"])
    assert error.value.code == "invalid_data"


def test_website_link_gets_https():
    assert services.parse_cv(_cv()).personal.website_url == "https://linkedin.com/in/sarakhan"
    cv = services.parse_cv(_cv(personal={"full_name": "S", "website": "http://sara.dev"}))
    assert cv.personal.website_url == "http://sara.dev"


def test_pdf_filename_keeps_name_letters():
    assert services.pdf_filename("Sara  Khan!") == "Sara_Khan_CV.pdf"
    assert services.pdf_filename("!!!") == "CV.pdf"


def test_contains_urdu():
    assert pdf_builder.contains_urdu(URDU_NAME)
    assert pdf_builder.contains_urdu("Aqib " + URDU_NAME)
    assert not pdf_builder.contains_urdu("Sara Khan")


# ── Templates and colours ───────────────────────────────────────────────────

def test_five_templates_each_with_a_thumbnail(client):
    assert services.TEMPLATES == ("modern", "classic", "minimal", "creative", "executive")
    html = client.get("/dashboard/cv-generator").get_data(as_text=True)
    for template in services.TEMPLATES:
        assert f'data-template="{template}"' in html
    assert html.count("<svg viewBox=\"0 0 60 78\"") == len(services.TEMPLATES)
    for accent in services.ACCENT_NAMES:
        assert f'data-accent="{accent}"' in html


@pytest.mark.parametrize("accent", services.ACCENT_NAMES)
def test_every_accent_colour_makes_a_pdf(client, accent):
    response = client.post("/api/cv-generator/pdf", json={
        "cv": _cv(), "template": "creative", "language": "en", "accent": accent})
    assert response.status_code == 200


def test_unknown_accent_is_rejected(client):
    response = client.post("/api/cv-generator/pdf", json={
        "cv": _cv(), "template": "modern", "language": "en", "accent": "pink"})
    assert response.status_code == 400
    assert response.get_json()["code"] == "accent_invalid"


def test_missing_accent_uses_the_default(client):
    assert _post(client).status_code == 200  # _post sends no accent
