"""Business rules for saved CVs (logged-in users): list, open, save, delete, and move a guest's
browser CVs into the account. Routes call these functions and never see the repository directly
(tests swap in a fake one, tests/fakes.py).

The form data is cleaned with the same rules as the PDF (services.parse_cv), except that an
unfinished CV may be saved without a name yet.
"""
import re

from app.blueprints.tools.cv_generator import services
from app.blueprints.tools.cv_generator.errors import CVError, CVNotFound
from app.blueprints.tools.cv_generator.repository import get_repository

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
    if not get_repository().delete_cv(access_token, cv_id):
        raise CVNotFound()


def import_cvs(access_token, guest_cvs):
    """Move a guest's browser CVs into the account. Each keeps its browser id as client_id, so
    retrying after a dropped connection never duplicates it. A CV that doesn't pass the checks
    is skipped rather than failing the whole move, and never more than the account has room for."""
    repo = get_repository()
    room = MAX_SAVED_CVS - len(repo.list_cvs(access_token, MAX_SAVED_CVS))
    rows = []
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
    return [_summary(row) for row in repo.import_cvs(access_token, rows)]


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
        "updated_at": row["updated_at"],
    }


def _full(row):
    result = _summary(row)
    result["cv"] = row.get("data") or {}
    return result
