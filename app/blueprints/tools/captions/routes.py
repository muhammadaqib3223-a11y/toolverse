from flask import current_app, g, jsonify, render_template, request

from app.blueprints.auth.decorators import login_optional
from app.blueprints.auth.session import current_auth_session
from app.blueprints.tools.captions import bp, services
from app.blueprints.tools.captions.errors import CaptionError
from app.blueprints.tools.captions.messages import error_message
from app.i18n import localized_route
from app.services.client_ip import ip_fingerprint

_ERROR_STATUS = {
    "login_required": 401,
    "not_found": 404,
    "limit_guest": 429,
    "limit_user": 429,
    "site_limit": 429,
    "ai_blocked": 422,
    "ai_quota": 503,
    "ai_unavailable": 503,
    "unavailable": 503,
}


@localized_route(bp, "/dashboard/captions", methods=["GET"])
@login_optional
def index():
    return render_template(
        "tools/captions/index.html",
        active_nav="captions",
        platforms=services.PLATFORMS,
        topic_max_length=services.TOPIC_MAX_LENGTH,
        guest_limit=current_app.config["CAPTIONS_GUEST_DAILY_LIMIT"],
    )


@localized_route(bp, "/api/captions/generate", methods=["POST"])
@login_optional
def api_generate():
    try:
        data = request.get_json(silent=True) or {}
        result = services.generate(_requester(), data.get("topic"), data.get("platform"))
        return jsonify(result)
    except CaptionError as error:
        return _error_response(error)


@localized_route(bp, "/api/captions/usage", methods=["GET"])
@login_optional
def api_usage():
    try:
        return jsonify(services.usage(_requester()))
    except CaptionError as error:
        return _error_response(error)


@localized_route(bp, "/api/captions/history", methods=["GET"])
@login_optional
def api_history():
    try:
        return jsonify(history=services.list_history(_access_token()))
    except CaptionError as error:
        return _error_response(error)


@localized_route(bp, "/api/captions/history/<caption_id>", methods=["DELETE"])
@login_optional
def api_delete_history(caption_id):
    try:
        services.delete_history(_access_token(), caption_id)
        return "", 204
    except CaptionError as error:
        return _error_response(error)


def _requester():
    auth_session = current_auth_session() if g.get("user") is not None else None
    return services.Requester(
        ip_hash=ip_fingerprint(),
        access_token=auth_session.access_token if auth_session else None,
    )


def _access_token():
    if g.get("user") is None:
        raise CaptionError("login_required")
    auth_session = current_auth_session()
    if auth_session is None:
        raise CaptionError("login_required")
    return auth_session.access_token


def _error_response(error):
    status = _ERROR_STATUS.get(error.code, 400)
    return jsonify(code=error.code, message=str(error_message(error))), status
