"""Language (English / Urdu) from the URL, and RTL support.

English pages have no prefix (/tools/notes); Urdu pages start with /ur (/ur/tools/notes).
Each URL always shows one language, which is what search engines need.
"""
from flask import current_app, has_request_context, request, url_for

URL_LANG_KEY = "lang_code"
PREFIXED_LANGUAGES = ("ur",)  # every language in config.LANGUAGES except the default
_LANG_SEGMENT = f"/<any({','.join(PREFIXED_LANGUAGES)}):{URL_LANG_KEY}>"


def _default_language():
    return current_app.config["BABEL_DEFAULT_LOCALE"]


def get_locale():
    """/ur or /ur/... is Urdu; every other URL is English."""
    if has_request_context():
        path = request.path
        for code in PREFIXED_LANGUAGES:
            if path == f"/{code}" or path.startswith(f"/{code}/"):
                return code
    return _default_language()


def localized_route(bp, rule, **options):
    """Register a view twice: at `rule` (English) and with the /ur prefix (Urdu)."""
    def decorator(view):
        bp.add_url_rule(rule, view_func=view, defaults={URL_LANG_KEY: None}, **options)
        bp.add_url_rule(_LANG_SEGMENT + ("" if rule == "/" else rule), view_func=view, **options)
        return view
    return decorator


def localized_url(endpoint, lang, **values):
    """URL of `endpoint` in language `lang` (the default language has no prefix)."""
    values[URL_LANG_KEY] = None if lang == _default_language() else lang
    return url_for(endpoint, **values)


def _has_language_versions(endpoint):
    return bool(endpoint) and current_app.url_map.is_endpoint_expecting(endpoint, URL_LANG_KEY)


def alternate_urls(external=True):
    """{language: URL} of the current page in every language, or {} if it has no language versions."""
    endpoint = request.endpoint
    if not _has_language_versions(endpoint):
        return {}
    args = request.view_args or {}
    return {
        code: localized_url(endpoint, code, _external=external, **args)
        for code in current_app.config["LANGUAGES"]
    }


def register_i18n(app):
    @app.url_value_preprocessor
    def drop_language_from_view_args(endpoint, values):
        # Views don't need the language argument; get_locale() reads it from the URL.
        if values:
            values.pop(URL_LANG_KEY, None)

    @app.url_defaults
    def keep_language_in_links(endpoint, values):
        # On an Urdu page, every url_for() link stays in Urdu unless a language is passed.
        if URL_LANG_KEY in values or not has_request_context():
            return
        lang = get_locale()
        if lang != _default_language() and _has_language_versions(endpoint):
            values[URL_LANG_KEY] = lang

    app.add_template_global(alternate_urls)

    @app.context_processor
    def inject_language():
        lang = get_locale()
        # Where the EN / اردو switch points: this page in the other language, or that language's home page.
        switch = alternate_urls(external=False) if has_request_context() else {}
        language_urls = {
            code: switch.get(code) or localized_url("marketing.index", code)
            for code in app.config["LANGUAGES"]
        }
        return {
            "current_lang": lang,
            "is_rtl": lang in app.config["RTL_LANGUAGES"],
            "languages": app.config["LANGUAGES"],
            "language_urls": language_urls,
        }
