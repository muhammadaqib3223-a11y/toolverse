"""App settings. Secrets come from environment variables (.env locally)."""
import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
    BEHIND_PROXY = False

    # Shown on the Privacy and Terms pages for questions and account deletion requests.
    CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "muhammadaqib3223@gmail.com")

    # Languages: code -> name shown in the language switcher.
    LANGUAGES = {"en": "English", "ur": "اردو"}
    RTL_LANGUAGES = frozenset({"ur"})
    BABEL_DEFAULT_LOCALE = "en"
    BABEL_DEFAULT_TIMEZONE = "UTC"

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # How long a user stays logged in without visiting (renewed on every visit).
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    # Supabase (Auth now; database and storage in later phases).
    # The publishable key (sb_publishable_...) is safe to use in the browser; the legacy anon key also works.
    # Never put the secret / service_role key here.
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    SUPABASE_PUBLISHABLE_KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
    SUPABASE_TIMEOUT_SECONDS = 10

    PASSWORD_MIN_LENGTH = 8   # must match Authentication -> Providers -> Email in Supabase
    PASSWORD_MAX_LENGTH = 72  # Supabase (bcrypt) ignores anything longer

    # CSRF tokens stay valid as long as the session, so a login form left open for hours still works.
    WTF_CSRF_TIME_LIMIT = None

    # AI (app/services/ai/). AI_PROVIDER picks the provider file; only that provider's key is needed.
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini").strip().lower()
    AI_TIMEOUT_SECONDS = 25
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    # Stable, free-tier model (checked against ai.google.dev/gemini-api/docs/models, Oct 2026).
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

    # Daily AI limits (reset at midnight UTC), counted by app/services/ai_quota.py.
    # The site limit covers ALL AI tools and everyone together, so the AI's free daily quota is
    # never used up. (CAPTIONS_SITE_DAILY_LIMIT is the old name, still read if set.)
    AI_SITE_DAILY_LIMIT = int(
        os.environ.get("AI_SITE_DAILY_LIMIT") or os.environ.get("CAPTIONS_SITE_DAILY_LIMIT") or "500"
    )
    CAPTIONS_GUEST_DAILY_LIMIT = int(os.environ.get("CAPTIONS_GUEST_DAILY_LIMIT", "3"))
    CAPTIONS_USER_DAILY_LIMIT = int(os.environ.get("CAPTIONS_USER_DAILY_LIMIT", "20"))
    # CV Generator "Improve with AI" (each button press is one try; "whole CV" is one try too).
    # An empty value in .env means "use the default".
    CV_AI_GUEST_DAILY_LIMIT = int(os.environ.get("CV_AI_GUEST_DAILY_LIMIT") or "3")
    CV_AI_USER_DAILY_LIMIT = int(os.environ.get("CV_AI_USER_DAILY_LIMIT") or "30")

    # CV Generator: the biggest request allowed for one CV (PDF or save; a full CV is ~10-20 KB),
    # and for moving all of a guest's browser CVs into the account at once.
    CV_MAX_REQUEST_BYTES = 64 * 1024
    CV_IMPORT_MAX_REQUEST_BYTES = 1024 * 1024


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SECRET_KEY = BaseConfig.SECRET_KEY or "dev-only-insecure-key"


class TestingConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = "test-only-secret-key"
    WTF_CSRF_ENABLED = False  # tests that check CSRF turn it back on
    SUPABASE_URL = "https://test-project.supabase.co"
    SUPABASE_PUBLISHABLE_KEY = "sb_publishable_test"
    GEMINI_API_KEY = ""  # tests use the fake provider in tests/fakes.py
    AI_SITE_DAILY_LIMIT = 500
    CAPTIONS_GUEST_DAILY_LIMIT = 3
    CAPTIONS_USER_DAILY_LIMIT = 20
    CV_AI_GUEST_DAILY_LIMIT = 3
    CV_AI_USER_DAILY_LIMIT = 30


class ProductionConfig(BaseConfig):
    SESSION_COOKIE_SECURE = True
    BEHIND_PROXY = True


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name=None):
    """Return the config class for `name` (or APP_ENV), failing loudly if it is unusable."""
    name = name or os.environ.get("APP_ENV", "development")
    try:
        config = CONFIGS[name]
    except KeyError:
        raise ValueError(f"Unknown APP_ENV '{name}'. Use one of: {', '.join(CONFIGS)}") from None

    if not config.SECRET_KEY:
        raise RuntimeError(f"SECRET_KEY must be set for the '{name}' environment.")
    return config
