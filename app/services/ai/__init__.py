"""Picks the AI provider named by AI_PROVIDER in config. Tools call get_ai_provider() and never
import a vendor file directly, so switching vendors is a new provider file + a config change.

Swappable for tests: app.extensions["ai_provider"] holds the active provider (tests/fakes.py).
"""
import importlib

from flask import current_app

from app.services.ai.base import AIBlocked, AIError, AIProvider, AIQuotaExceeded, AIUnavailable

# name -> "module:Class". Imported only when chosen, so an unused vendor's SDK is never loaded.
PROVIDERS = {
    "gemini": "app.services.ai.gemini:GeminiProvider",
}

__all__ = [
    "AIBlocked", "AIError", "AIProvider", "AIQuotaExceeded", "AIUnavailable",
    "create_ai_provider", "get_ai_provider", "init_ai",
]


def create_ai_provider(config):
    name = (config.get("AI_PROVIDER") or "").strip().lower()
    try:
        module_name, class_name = PROVIDERS[name].split(":")
    except KeyError:
        raise ValueError(f"Unknown AI_PROVIDER '{name}'. Use one of: {', '.join(PROVIDERS)}") from None
    provider_class = getattr(importlib.import_module(module_name), class_name)
    return provider_class.from_config(config)


def init_ai(app):
    app.extensions["ai_provider"] = create_ai_provider(app.config)


def get_ai_provider() -> AIProvider:
    return current_app.extensions["ai_provider"]
