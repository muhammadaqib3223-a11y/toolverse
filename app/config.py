"""App settings. Secrets come from environment variables (.env locally)."""
import os

from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
    BEHIND_PROXY = False

    # Languages: code -> name shown in the language switcher.
    LANGUAGES = {"en": "English", "ur": "اردو"}
    RTL_LANGUAGES = frozenset({"ur"})
    BABEL_DEFAULT_LOCALE = "en"
    BABEL_DEFAULT_TIMEZONE = "UTC"

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SECRET_KEY = BaseConfig.SECRET_KEY or "dev-only-insecure-key"


class TestingConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = "test-only-secret-key"


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
