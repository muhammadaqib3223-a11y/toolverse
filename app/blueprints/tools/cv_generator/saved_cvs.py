"""Business rules for saved CVs (logged-in users): list, open, save, delete, and move a guest's
browser CVs into the account. Routes call these functions and never see the repository directly
(tests swap in a fake one, tests/fakes.py).

The form data is cleaned with the same rules as the PDF (services.parse_cv), except that an
unfinished CV may be saved without a name yet.

Photos live in the private Storage bucket as <user id>/<cv id>.jpg (one per CV), after
services.clean_photo() has checked them and removed hidden data.
"""
import logging
import re

from app.blueprints.tools.cv_generator import services
from app.blueprints.tools.cv_generator.errors import CVError, CVNotFound
from app.blueprints.tools.cv_generator.repository import get_repository

logger = logging.getLogger(__name__)

MAX_SAVED_CVS = 20  # also enforced by the database (20261015_cvs.sql)
TITLE_MAX_LENGTH = 120
DEFAULT_TITLE = "CV"

_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def list_cvs(access_token):
    return [_summary(row) for row in get_repository().list_cvs(access_token, MAX_SAVED_CVS)]


def get_cv(access_token, cv_id):
    _check_id(cv_id)
    row = get_repository().get_cv(access_token, cv_id)
    if row is None:
        raise CVNotFound()
    return _full(row)


def create_cv(access_token, payload):
    row = _clean_payload(payload)
    return _full(get_repository().insert_cv(access_token, row))


def update_cv(access_token, cv_id, payload):
    _check_id(cv_id)
    row = get_repository().update_cv(access_token, cv_id, _clean_payload(payload))
    if row is None:
        raise CVNotFound()
    return _full(row)


def delete_cv(access_token, cv_id):
    _check_id(cv_id)
    repo = get_repository()
    row = repo.get_cv(access_token, cv_id)
    if row is None or not repo.delete_cv(access_token, cv_id):
        raise CVNotFound()
    if row.get("photo_path"):
        _delete_photo_file(access_token, row["photo_path"])


def set_photo(access_token, user_id, cv_id, data_url):
    """Check the photo, store it for this CV (replacing any old one) and return the CV summary."""
    _check_id(cv_id)
    jpeg = services.clean_photo(data_url)
    repo = get_repository()
    if repo.get_cv(access_token, cv_id) is None:
        raise CVNotFound()
    path = _photo_path(user_id, cv_id)
    repo.upload_photo(access_token, path, jpeg)
    row = repo.set_photo_path(access_token, cv_id, path)
    if row is None:
        raise CVNotFound()
    return _summary(row)


def get_photo(access_token, cv_id):
    """The CV's photo as JPEG bytes, or CVNotFound if it has none."""
    _check_id(cv_id)
    repo = get_repository()
    row = repo.get_cv(access_token, cv_id)
    if row is None or not row.get("photo_path"):
        raise CVNotFound()
    photo = repo.download_photo(access_token, row["photo_path"])
    if photo is None:
        raise CVNotFound()
    return photo


def remove_photo(access_token, cv_id):
    _check_id(cv_id)
    repo = get_repository()
    row = repo.get_cv(access_token, cv_id)
    if row is None:
        raise CVNotFound()
    if row.get("photo_path"):
        repo.set_photo_path(access_token, cv_id, None)
        _delete_photo_file(access_token, row["photo_path"])


def import_cvs(access_token, guest_cvs, user_id):
    """Move a guest's browser CVs into the account. Each keeps its browser id as client_id, so
    retrying after a dropped connection never duplicates it. A CV that doesn't pass the checks
    is skipped rather than failing the whole move, and never more than the account has room for."""
    repo = get_repository()
    room = MAX_SAVED_CVS - len(repo.list_cvs(access_token, MAX_SAVED_CVS))
    rows, photos = [], {}
    for item in guest_cvs if isinstance(guest_cvs, list) else []:
        if len(rows) >= room:
            break
        if not isinstance(item, dict) or not _UUID_RE.match(str(item.get("id") or "")):
            continue
        try:
            row = _clean_payload(item)
        except CVError:
            continue
        row["client_id"] = item["id"]
        rows.append(row)
        if item.get("photo"):
            photos[item["id"]] = item["photo"]

    imported = repo.import_cvs(access_token, rows)
    result = []
    for row in imported:
        photo = photos.get(row.get("client_id"))
        if photo:
            row = _import_photo(access_token, user_id, row, photo)
        result.append(_summary(row))
    return result


# ── Helpers ──────────────────────────────────────────────────────────────────

def _clean_payload(payload):
    if not isinstance(payload, dict):
        raise CVError("invalid_data")
    template = payload.get("template") or services.DEFAULT_TEMPLATE
    language = payload.get("language") or "en"
    template, language, accent = services.check_design(template, language, payload.get("accent"))
    cv = services.parse_cv(payload.get("cv") or {}, require_name=False)
    return {
        "title": _title(payload.get("title"), cv),
        "data": services.cv_to_dict(cv),
        "template": template,
        "accent": accent,
        "language": language,
    }


def _title(raw, cv):
    if raw is not None and not isinstance(raw, str):
        raise CVError("invalid_data", "title")
    title = " ".join((raw or "").split())
    if len(title) > TITLE_MAX_LENGTH:
        raise CVError("title_too_long", "title")
    return title or cv.personal.full_name or DEFAULT_TITLE


def _import_photo(access_token, user_id, row, data_url):
    """Store a moved guest CV's photo. A photo that fails is skipped: the CV itself is safe."""
    try:
        jpeg = services.clean_photo(data_url)
        path = _photo_path(user_id, row["id"])
        get_repository().upload_photo(access_token, path, jpeg)
        return get_repository().set_photo_path(access_token, row["id"], path) or row
    except CVError as error:
        logger.warning("Guest CV photo not moved (%s)", error.code)
        return row


def _photo_path(user_id, cv_id):
    if not _UUID_RE.match(str(user_id or "")):
        raise CVError("login_required")
    return f"{str(user_id).lower()}/{str(cv_id).lower()}.jpg"


def _delete_photo_file(access_token, path):
    try:
        get_repository().delete_photo(access_token, path)
    except CVError:
        # The CV row is already gone or updated; a left-over file is only reachable by its owner.
        logger.warning("Could not delete CV photo %s", path)


def _check_id(cv_id):
    if not cv_id or not _UUID_RE.match(str(cv_id)):
        raise CVNotFound()


def _summary(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "template": row["template"],
        "accent": row["accent"],
        "language": row["language"],
        "has_photo": bool(row.get("photo_path")),
        "updated_at": row["updated_at"],
    }


def _full(row):
    result = _summary(row)
    result["cv"] = row.get("data") or {}
    return result
