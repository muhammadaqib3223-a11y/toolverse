"""HTTP routes for the CV Generator.

The page (`/dashboard/cv-generator`) is open to guests too. A guest's CVs stay in the browser
(public/static/js/cv_generator/stores.js); a logged-in user's CVs are saved in Supabase through
the /api/cvs routes below (JSON `login_required` for guests, never a redirect).
"Make my PDF" works for everyone and stores nothing: the CV goes in, the PDF comes out.
"""
from urllib.parse import quote

from flask import Response, current_app, g, jsonify, render_template, request
from flask_babel import get_locale

from app.blueprints.auth.decorators import login_optional
from app.blueprints.auth.session import current_auth_session
from app.blueprints.tools.cv_generator import bp, saved_cvs, services
from app.blueprints.tools.cv_generator.errors import CVError
from app.blueprints.tools.cv_generator.messages import error_message
from app.blueprints.tools.cv_generator.pdf_templates import ACCENT_HEX, ATS_SAFEST, DEFAULT_ACCENT
from app.i18n import localized_route

# Every other CVError is a bad request (400): a problem the user can fix in the form.
_ERROR_STATUS = {
    "login_required": 401,
    "not_found": 404,
    "cv_limit": 409,
    "too_large": 413,
    "pdf_failed": 500,
    "unavailable": 503,
}


@localized_route(bp, "/dashboard/cv-generator", methods=["GET"])
@login_optional
def index():
    locale = str(get_locale())
    return render_template(
        "tools/cv_generator/index.html",
        active_nav="cv-generator",
        templates=services.TEMPLATES,
        default_template=services.DEFAULT_TEMPLATE,
        ats_safest=ATS_SAFEST,
        accents=ACCENT_HEX,
        default_accent=DEFAULT_ACCENT,
        cv_language=locale if locale in services.LANGUAGES else "en",
        limits=services.LIMITS,
        title_max_length=saved_cvs.TITLE_MAX_LENGTH,
        max_saved_cvs=saved_cvs.MAX_SAVED_CVS,
        max_experience=services.MAX_EXPERIENCE,
        max_education=services.MAX_EDUCATION,
        max_skills=services.MAX_SKILLS,
    )


@localized_route(bp, "/api/cv-generator/pdf", methods=["POST"])
@login_optional
def api_pdf():
    try:
        data = _json_body()
        pdf = services.build_pdf(data.get("cv"), data.get("template"), data.get("language"), data.get("accent"))
    except CVError as error:
        return _error_response(error)

    response = Response(pdf.content, mimetype="application/pdf")
    response.headers["Content-Disposition"] = _attachment(pdf.filename)
    # The PDF holds personal details: never keep it in a shared cache.
    response.headers["Cache-Control"] = "private, no-store"
    return response


@localized_route(bp, "/api/cvs", methods=["GET", "POST"])
@login_optional
def api_cvs():
    try:
        access_token = _access_token()
        if request.method == "POST":
            return jsonify(cv=saved_cvs.create_cv(access_token, _json_body())), 201
        return jsonify(cvs=saved_cvs.list_cvs(access_token))
    except CVError as error:
        return _error_response(error)


@localized_route(bp, "/api/cvs/<cv_id>", methods=["GET", "PATCH", "DELETE"])
@login_optional
def api_cv(cv_id):
    try:
        access_token = _access_token()
        if request.method == "DELETE":
            saved_cvs.delete_cv(access_token, cv_id)
            return "", 204
        if request.method == "PATCH":
            return jsonify(cv=saved_cvs.update_cv(access_token, cv_id, _json_body()))
        return jsonify(cv=saved_cvs.get_cv(access_token, cv_id))
    except CVError as error:
        return _error_response(error)


@localized_route(bp, "/api/cvs/import", methods=["POST"])
@login_optional
def api_import():
    try:
        access_token = _access_token()
        data = _json_body(current_app.config["CV_IMPORT_MAX_REQUEST_BYTES"])
        return jsonify(cvs=saved_cvs.import_cvs(access_token, data.get("cvs") or []))
    except CVError as error:
        return _error_response(error)


def _access_token():
    """The logged-in user's current access token, or a CVError("login_required")."""
    if g.get("user") is None:
        raise CVError("login_required")
    auth_session = current_auth_session()
    if auth_session is None:
        raise CVError("login_required")
    return auth_session.access_token


def _json_body(max_bytes=None):
    max_bytes = max_bytes or current_app.config["CV_MAX_REQUEST_BYTES"]
    if request.content_length is not None and request.content_length > max_bytes:
        raise CVError("too_large")
    # Also stops a body sent without a Content-Length from growing past the limit.
    request.max_content_length = max_bytes
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise CVError("invalid_data")
    return data


def _attachment(filename):
    """Content-Disposition with an ASCII fallback name plus the real (possibly Urdu) name."""
    ascii_name = filename.encode("ascii", "ignore").decode().lstrip("_") or "CV.pdf"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def _error_response(error):
    status = _ERROR_STATUS.get(error.code, 400)
    return jsonify(code=error.code, field=error.field, message=str(error_message(error))), status
