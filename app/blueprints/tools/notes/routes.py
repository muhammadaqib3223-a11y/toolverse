"""HTTP routes for the Notes tool.

The page (`/dashboard/notes`) is open to guests too: they keep their notes in the browser
(see public/static/js/notes/) and the page's JavaScript never calls the API below for them.
The JSON API only works for logged-in users; it is what the page calls to list, save, delete
and search notes, and to move guest notes into the account once they log in.
"""
from flask import g, jsonify, render_template, request

from app.blueprints.auth.decorators import login_optional
from app.blueprints.auth.session import current_auth_session
from app.blueprints.tools.notes import bp, services
from app.blueprints.tools.notes.errors import NoteError
from app.blueprints.tools.notes.messages import error_message
from app.i18n import localized_route

# Every other NoteError is a bad request (400): a validation problem the user can fix.
_ERROR_STATUS = {
    "login_required": 401,
    "not_found": 404,
    "unavailable": 503,
}


@localized_route(bp, "/dashboard/notes", methods=["GET"])
@login_optional
def index():
    return render_template("tools/notes/index.html", active_nav="notes")


@localized_route(bp, "/api/notes", methods=["GET", "POST"])
@login_optional
def api_notes():
    try:
        access_token = _access_token()
        if request.method == "POST":
            return _create_note(access_token)
        return _list_notes(access_token)
    except NoteError as error:
        return _error_response(error)


@localized_route(bp, "/api/notes/<note_id>", methods=["PATCH", "DELETE"])
@login_optional
def api_note(note_id):
    try:
        access_token = _access_token()
        if request.method == "DELETE":
            services.delete_note(access_token, note_id)
            return "", 204
        data = request.get_json(silent=True) or {}
        note = services.update_note(access_token, note_id, data.get("title", ""), data.get("content", ""))
        return jsonify(note=note)
    except NoteError as error:
        return _error_response(error)


@localized_route(bp, "/api/notes/import", methods=["POST"])
@login_optional
def api_import():
    try:
        access_token = _access_token()
        data = request.get_json(silent=True) or {}
        notes = services.import_notes(access_token, data.get("notes") or [])
        return jsonify(notes=notes)
    except NoteError as error:
        return _error_response(error)


def _list_notes(access_token):
    search = (request.args.get("search") or "").strip() or None
    offset = _int_arg("offset", 0)
    limit = _int_arg("limit", services.PAGE_SIZE, maximum=services.PAGE_SIZE)
    notes, has_more = services.list_notes(access_token, search=search, offset=offset, limit=limit)
    return jsonify(notes=notes, has_more=has_more)


def _create_note(access_token):
    data = request.get_json(silent=True) or {}
    note = services.create_note(access_token, data.get("title", ""), data.get("content", ""))
    return jsonify(note=note), 201


def _access_token():
    """The logged-in user's current access token, or a NoteError("login_required")."""
    if g.get("user") is None:
        raise NoteError("login_required")
    auth_session = current_auth_session()
    if auth_session is None:
        raise NoteError("login_required")
    return auth_session.access_token


def _int_arg(name, default, maximum=None):
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        value = default
    value = max(value, 0)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _error_response(error):
    status = _ERROR_STATUS.get(error.code, 400)
    return jsonify(code=error.code, message=str(error_message(error))), status
