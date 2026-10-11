"""CV Generator extra sections (projects, certifications, languages, hobbies, references,
LinkedIn) and the profile photo: cleaning, PDF text, privacy (no hidden photo data) and Storage
for saved CVs. Fakes only, never Supabase."""
import base64
import io
import uuid

import pytest
from PIL import Image
from pypdf import PdfReader

from app.blueprints.tools.cv_generator import services
from app.services import pdf_builder, photos


def _image_data_url(size=(600, 800), fmt="PNG", exif_gps=False):
    image = Image.new("RGB", size, (180, 140, 120))
    buffer = io.BytesIO()
    if exif_gps:
        exif = Image.Exif()
        exif[0x8825] = {2: (24.0, 52.0, 0.0)}  # GPSInfo: latitude
        exif[0x010F] = "SecretPhoneMaker"      # camera maker
        image.save(buffer, "JPEG", exif=exif)
        mime = "jpeg"
    else:
        image.save(buffer, fmt)
        mime = fmt.lower()
    return f"data:image/{mime};base64," + base64.b64encode(buffer.getvalue()).decode()


def _full_cv():
    return {
        "personal": {"full_name": "Sara Khan", "headline": "Data Analyst", "email": "sara@example.com",
                     "linkedin": "linkedin.com/in/sarakhan"},
        "summary": "Analyst.",
        "experience": [{"job_title": "Analyst", "company": "Daraz"}],
        "projects": [{"name": "Sales Forecast", "link": "github.com/sara/forecast", "description": "- Built a model"},
                     {"name": "", "link": "", "description": ""}],
        "certifications": [{"name": "Google Data Analytics", "issuer": "Coursera", "date": "2023"}],
        "languages": [{"name": "English", "level": "fluent"}, {"name": "Urdu", "level": "native"},
                      {"name": "english", "level": "basic"}],
        "hobbies": ["Chess", "chess", "Cricket"],
        "references": [{"name": "Ali Raza", "title": "Manager, Daraz", "contact": "ali@example.com"}],
    }


def _pdf(client, cv, template="classic", photo=None, language="en"):
    body = {"cv": cv, "template": template, "language": language}
    if photo is not None:
        body["photo"] = photo
    return client.post("/api/cv-generator/pdf", json=body)


def _text(data):
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() for page in reader.pages).replace(pdf_builder.INVISIBLE_GLYPH_TEXT, "")


# ── New sections ────────────────────────────────────────────────────────────

def test_new_sections_are_cleaned():
    cv = services.parse_cv(_full_cv())
    assert cv.personal.linkedin_url == "https://linkedin.com/in/sarakhan"
    assert [p.name for p in cv.projects] == ["Sales Forecast"]
    assert [(l.name, l.level) for l in cv.languages] == [("English", "fluent"), ("Urdu", "native")]
    assert cv.hobbies == ("Chess", "Cricket")
    assert cv.references[0].contact == "ali@example.com"


@pytest.mark.parametrize("template", services.TEMPLATES)
def test_new_sections_are_in_every_pdf_as_text(client, template):
    response = _pdf(client, _full_cv(), template)
    assert response.status_code == 200
    text = _text(response.data)
    for expected in ("linkedin.com/in/sarakhan", "Sales Forecast", "Google Data Analytics", "Coursera",
                     "English (Fluent)", "Urdu (Native)", "Chess", "Ali Raza", "PROJECTS", "LANGUAGES"):
        assert expected in text, (template, expected)


def test_empty_sections_are_left_out(client):
    text = _text(_pdf(client, {"personal": {"full_name": "Sara Khan"}, "summary": "Hi."}).data)
    for heading in ("PROJECTS", "CERTIFICATIONS", "LANGUAGES", "HOBBIES", "REFERENCES", "EXPERIENCE"):
        assert heading not in text


def test_references_on_request(client):
    cv = {"personal": {"full_name": "Sara Khan"}, "references_on_request": True}
    assert "References available on request." in _text(_pdf(client, cv).data)


def test_urdu_cv_has_urdu_section_names(client):
    response = _pdf(client, _full_cv(), "modern", language="ur")
    text = _text(response.data)
    assert "زبانیں" in text and "منصوبے" in text


@pytest.mark.parametrize("cv, code, field", [
    ({"personal": {"full_name": "S"}, "languages": [{"name": "English", "level": "god"}]}, "invalid_data", "languages.0.level"),
    ({"personal": {"full_name": "S", "linkedin": "javascript:x"}}, "website_invalid", "personal.linkedin"),
    ({"personal": {"full_name": "S"}, "projects": [{"name": "P", "link": "not a link"}]}, "website_invalid", "projects.0.link"),
    ({"personal": {"full_name": "S"}, "hobbies": ["h%d" % i for i in range(services.MAX_HOBBIES + 1)]}, "too_many_hobbies", "hobbies"),
    ({"personal": {"full_name": "S"}, "references": [{"name": "R"}] * (services.MAX_REFERENCES + 1)}, "too_many_references", "references"),
])
def test_bad_new_section_data(client, cv, code, field):
    body = _pdf(client, cv).get_json()
    assert (body["code"], body["field"]) == (code, field)
    assert body["message"]


# ── Photo cleaning ──────────────────────────────────────────────────────────

def test_photo_is_cropped_square_resized_and_jpeg():
    jpeg = photos.clean_data_url(_image_data_url((1200, 900)))
    with Image.open(io.BytesIO(jpeg)) as image:
        assert image.format == "JPEG"
        assert image.size == (photos.MAX_SIDE, photos.MAX_SIDE)


def test_photo_hidden_data_is_removed():
    jpeg = photos.clean_data_url(_image_data_url(exif_gps=True))
    assert b"SecretPhoneMaker" not in jpeg
    with Image.open(io.BytesIO(jpeg)) as image:
        assert not image.getexif()


@pytest.mark.parametrize("data_url, code", [
    ("data:image/gif;base64,R0lGODlhAQABAAAAACw=", "photo_invalid"),
    ("data:image/png;base64,bm90IGFuIGltYWdl", "photo_invalid"),       # "not an image"
    ("https://example.com/me.jpg", "photo_invalid"),
    ("HUGE", "photo_too_large"),
])
def test_bad_photos_are_rejected(data_url, code):
    if data_url == "HUGE":  # built here: a huge test parameter would end up in pytest's env vars
        data_url = "data:image/png;base64," + "A" * (photos.MAX_UPLOAD_BYTES * 2)
    with pytest.raises(photos.PhotoError) as error:
        photos.clean_data_url(data_url)
    assert error.value.code == code


def test_tiny_photo_is_rejected():
    with pytest.raises(photos.PhotoError):
        photos.clean_data_url(_image_data_url((20, 20)))


@pytest.mark.parametrize("template", services.TEMPLATES)
def test_pdf_with_photo_keeps_selectable_text(client, template):
    response = _pdf(client, _full_cv(), template, photo=_image_data_url())
    assert response.status_code == 200
    assert b"/Image" in response.data or b"/XObject" in response.data
    assert "Sara Khan" in _text(response.data)


def test_pdf_with_bad_photo_says_so(client):
    body = _pdf(client, _full_cv(), photo="data:image/png;base64,bm9wZQ==").get_json()
    assert (body["code"], body["field"]) == ("photo_invalid", "photo")


# ── Photos of saved CVs (Storage) ───────────────────────────────────────────

@pytest.fixture
def user(client, log_in, cvs_repository, auth_service):
    log_in()
    user_id = auth_service.users["sara@example.com"].id
    cv_id = client.post("/api/cvs", json={"title": "Mine", "cv": _full_cv(), "template": "modern"}).get_json()["cv"]["id"]
    return cvs_repository, user_id, cv_id


def test_photo_upload_download_remove(client, user):
    repo, user_id, cv_id = user
    response = client.put(f"/api/cvs/{cv_id}/photo", json={"photo": _image_data_url()})
    assert response.status_code == 200
    assert response.get_json()["cv"]["has_photo"] is True
    path = f"{user_id}/{cv_id}.jpg"
    assert path in repo.photos  # the user's own folder, named by the CV

    photo = client.get(f"/api/cvs/{cv_id}/photo")
    assert photo.status_code == 200 and photo.mimetype == "image/jpeg"
    assert photo.headers["Cache-Control"] == "private, no-store"
    assert client.get("/api/cvs").get_json()["cvs"][0]["has_photo"] is True

    assert client.delete(f"/api/cvs/{cv_id}/photo").status_code == 204
    assert path not in repo.photos
    assert client.get(f"/api/cvs/{cv_id}/photo").status_code == 404


def test_deleting_a_cv_deletes_its_photo(client, user):
    repo, _user_id, cv_id = user
    client.put(f"/api/cvs/{cv_id}/photo", json={"photo": _image_data_url()})
    assert client.delete(f"/api/cvs/{cv_id}").status_code == 204
    assert repo.photos == {}


def test_bad_photo_upload_stores_nothing(client, user):
    repo, _user_id, cv_id = user
    response = client.put(f"/api/cvs/{cv_id}/photo", json={"photo": "data:image/png;base64,bm9wZQ=="})
    assert response.status_code == 400
    assert repo.photos == {}


def test_photo_of_someone_elses_cv_is_not_found(client, log_in, user):
    _repo, _user_id, cv_id = user
    log_in("ali@example.com", name="Ali")
    assert client.put(f"/api/cvs/{cv_id}/photo", json={"photo": _image_data_url()}).status_code == 404
    assert client.get(f"/api/cvs/{cv_id}/photo").status_code == 404


def test_guests_cannot_use_photo_storage(client, cvs_repository):
    cv_id = uuid.uuid4()
    assert client.put(f"/api/cvs/{cv_id}/photo", json={"photo": _image_data_url()}).status_code == 401
    assert client.get(f"/api/cvs/{cv_id}/photo").status_code == 401


def test_guest_cv_photo_moves_with_the_cv(client, log_in, cvs_repository, auth_service):
    log_in()
    user_id = auth_service.users["sara@example.com"].id
    guest = {"id": str(uuid.uuid4()), "title": "Guest", "cv": _full_cv(), "template": "modern",
             "accent": "teal", "language": "en", "photo": _image_data_url()}
    moved = client.post("/api/cvs/import", json={"cvs": [guest]}).get_json()["cvs"]
    assert moved[0]["has_photo"] is True
    assert f"{user_id}/{moved[0]['id']}.jpg" in cvs_repository.photos
