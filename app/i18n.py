"""Language selection (English / Urdu) and RTL support."""
from flask import current_app, request, session

SESSION_KEY = "lang"


def get_locale():
    """Pick the language: the user's saved choice, else their browser's preference."""
    supported = current_app.config["LANGUAGES"]
    chosen = session.get(SESSION_KEY)
    if chosen in supported:
        return chosen
    return (
        request.accept_languages.best_match(supported.keys())
        or current_app.config["BABEL_DEFAULT_LOCALE"]
    )


def set_language(code):
    """Remember `code` as the user's language. Returns False if it is not supported."""
    if code not in current_app.config["LANGUAGES"]:
        return False
    session[SESSION_KEY] = code
    session.permanent = True
    return True


def register_i18n(app):
    @app.context_processor
    def inject_language():
        lang = get_locale()
        return {
            "current_lang": lang,
            "is_rtl": lang in app.config["RTL_LANGUAGES"],
            "languages": app.config["LANGUAGES"],
        }
