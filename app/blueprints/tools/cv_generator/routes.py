"""HTTP routes for the CV Generator.

The page (`/dashboard/cv-generator`) is open to guests too. The form is kept in the browser
(public/static/js/cv_generator/); the only API call is "make my PDF", which works without login
and stores nothing: the CV goes in, the PDF comes out.
"""
from urllib.parse import quote

from flask import Response, current_app, jsonify, render_template, request
from flask_babel import get_locale

from app.blueprints.auth.decorators import login_optional
from app.blueprints.tools.cv_generator import bp, services
from app.blueprints.tools.cv_generator.errors import CVError
from app.blueprints.tools.cv_generator.messages import error_message
from app.i18n import localized_route

# Every other CVError is a bad request (400): a problem the user can fix in the form.
_ERROR_STATUS = {
    "too_large": 413,
    "pdf_failed": 500,
}


@localized_route(bp, "/dashboard/cv-generator", methods=["GET"])
@login_optional
def index():
    return render_template(
        "tools/cv_generator/index.html",
        active_nav="cv-generator",
        templates=services.TEMPLATES,
        cv_language=str(get_locale()) if str(get_locale()) in services.LANGUAGES else "en",
        limits=services.LIMITS,
        max_experience=services.MAX_EXPERIENCE,
        max_education=services.MAX_EDUCATION,
        max_skills=services.MAX_SKILLS,
    )


@localized_route(bp, "/api/cv-generator/pdf", methods=["POST"])
@login_optional
def api_pdf():
    try:
        data = _json_body()
        pdf = services.build_pdf(data.get("cv"), data.get("template"), data.get("language"))
    except CVError as error:
        return _error_response(error)

    response = Response(pdf.content, mimetype="application/pdf")
    response.headers["Content-Disposition"] = _attachment(pdf.filename)
    # The PDF holds personal details: never keep it in a shared cache.
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _json_body():
    max_bytes = current_app.config["CV_PDF_MAX_REQUEST_BYTES"]
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
