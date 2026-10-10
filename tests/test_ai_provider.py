"""The swappable AI layer (app/services/ai/) and the Gemini provider. Never calls Google."""
from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors

from app.services.ai import create_ai_provider, get_ai_provider
from app.services.ai.base import AIBlocked, AIQuotaExceeded, AIUnavailable
from app.services.ai.gemini import GeminiProvider

SCHEMA = {"type": "object"}


def _config(**overrides):
    config = {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "gemini-test", "AI_TIMEOUT_SECONDS": 5}
    config.update(overrides)
    return config


def _response(text='{"captions": ["a"]}', finish_reason="STOP", block_reason=None):
    return SimpleNamespace(
        text=text,
        prompt_feedback=SimpleNamespace(block_reason=block_reason) if block_reason else None,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(value=finish_reason))],
    )


class _FakeModels:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def _provider_with(models):
    provider = GeminiProvider(api_key="test-key", model="gemini-test", timeout_seconds=5)
    provider._client = SimpleNamespace(models=models)
    return provider


def _generate(provider):
    return provider.generate_json(system="sys", prompt="hi", schema=SCHEMA)


# ── Choosing the provider ───────────────────────────────────────────────────

def test_app_uses_the_configured_provider(app):
    with app.app_context():
        assert isinstance(get_ai_provider(), GeminiProvider)


def test_provider_reads_model_and_key_from_config():
    provider = create_ai_provider(_config(GEMINI_MODEL="gemini-x"))
    assert isinstance(provider, GeminiProvider)
    assert provider.model == "gemini-x"


def test_default_model_is_the_free_tier_flash_lite(app):
    assert app.config["GEMINI_MODEL"] == "gemini-3.5-flash-lite"


def test_unknown_provider_fails_loudly():
    with pytest.raises(ValueError, match="AI_PROVIDER"):
        create_ai_provider(_config(AI_PROVIDER="nope"))


# ── Gemini ──────────────────────────────────────────────────────────────────

def test_missing_api_key_is_unavailable_without_any_network():
    provider = GeminiProvider(api_key="", model="gemini-test", timeout_seconds=5)
    with pytest.raises(AIUnavailable):
        _generate(provider)


def test_returns_parsed_json_and_sends_model_and_schema():
    models = _FakeModels(response=_response('{"captions": ["one", "two"]}'))
    assert _generate(_provider_with(models)) == {"captions": ["one", "two"]}
    call = models.calls[0]
    assert call["model"] == "gemini-test"
    assert call["contents"] == "hi"
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].response_json_schema == SCHEMA
    assert call["config"].system_instruction == "sys"


def test_rate_limit_becomes_quota_error():
    error = genai_errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    with pytest.raises(AIQuotaExceeded):
        _generate(_provider_with(_FakeModels(error=error)))


def test_server_error_becomes_unavailable():
    error = genai_errors.ServerError(503, {"error": {"code": 503, "message": "down", "status": "UNAVAILABLE"}})
    with pytest.raises(AIUnavailable):
        _generate(_provider_with(_FakeModels(error=error)))


def test_network_error_becomes_unavailable():
    import httpx
    with pytest.raises(AIUnavailable):
        _generate(_provider_with(_FakeModels(error=httpx.ConnectTimeout("slow"))))


def test_blocked_prompt_becomes_blocked():
    with pytest.raises(AIBlocked):
        _generate(_provider_with(_FakeModels(response=_response(block_reason="SAFETY"))))


def test_safety_stop_becomes_blocked():
    with pytest.raises(AIBlocked):
        _generate(_provider_with(_FakeModels(response=_response(text=None, finish_reason="SAFETY"))))


def test_invalid_json_becomes_unavailable():
    with pytest.raises(AIUnavailable):
        _generate(_provider_with(_FakeModels(response=_response(text="not json"))))


def test_empty_answer_becomes_unavailable():
    with pytest.raises(AIUnavailable):
        _generate(_provider_with(_FakeModels(response=_response(text=""))))
