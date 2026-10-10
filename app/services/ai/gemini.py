"""Google Gemini, through the official google-genai SDK. The only file that imports it.

Model and key come from config (GEMINI_MODEL, GEMINI_API_KEY). Free tier: Google may use the
prompts to improve its products, which the Privacy Policy says.
"""
import json
import logging

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.services.ai.base import AIBlocked, AIProvider, AIQuotaExceeded, AIUnavailable

logger = logging.getLogger(__name__)

# Finish reasons that mean "the model refused", not "something broke".
_BLOCKED_REASONS = {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "LANGUAGE"}


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_key, model, timeout_seconds):
        self.model = model
        self._timeout_ms = int(timeout_seconds * 1000)
        self._api_key = api_key
        self._client = None  # made on first use, then reused (it is thread-safe)

    @classmethod
    def from_config(cls, config):
        return cls(
            api_key=config.get("GEMINI_API_KEY", ""),
            model=config["GEMINI_MODEL"],
            timeout_seconds=config["AI_TIMEOUT_SECONDS"],
        )

    def generate_json(self, *, system, prompt, schema, temperature=0.9, max_output_tokens=2048):
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json",
            response_json_schema=schema,
        )
        try:
            response = self._get_client().models.generate_content(
                model=self.model, contents=prompt, config=config
            )
        except genai_errors.APIError as error:
            raise self._translate(error) from None
        except (httpx.HTTPError, OSError) as error:
            logger.warning("Gemini network error: %s", error)
            raise AIUnavailable("network") from None

        return self._parse(response)

    def _get_client(self):
        if not self._api_key:
            logger.error("Gemini is not configured: set GEMINI_API_KEY")
            raise AIUnavailable("not_configured")
        if self._client is None:
            # attempts=1: never retry by ourselves. A retry would quietly use up another
            # request of the free quota; the user can press the button again instead.
            self._client = genai.Client(
                api_key=self._api_key,
                http_options=types.HttpOptions(
                    timeout=self._timeout_ms,
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
        return self._client

    def _translate(self, error):
        code = getattr(error, "code", None)
        if code == 429:
            logger.warning("Gemini quota/rate limit hit (model %s): %s", self.model, error.message)
            return AIQuotaExceeded(str(code))
        logger.error("Gemini API error %s (model %s): %s", code, self.model, getattr(error, "message", error))
        return AIUnavailable(str(code))

    def _parse(self, response):
        feedback = getattr(response, "prompt_feedback", None)
        if feedback is not None and getattr(feedback, "block_reason", None):
            logger.info("Gemini blocked the prompt: %s", feedback.block_reason)
            raise AIBlocked(str(feedback.block_reason))

        candidates = getattr(response, "candidates", None) or []
        if candidates:
            reason = getattr(candidates[0], "finish_reason", None)
            reason_name = getattr(reason, "value", reason)
            if reason_name in _BLOCKED_REASONS:
                logger.info("Gemini stopped for %s", reason_name)
                raise AIBlocked(str(reason_name))

        text = getattr(response, "text", None)
        if not text:
            logger.warning("Gemini returned no text")
            raise AIUnavailable("empty")
        try:
            return json.loads(text)
        except ValueError:
            logger.warning("Gemini returned invalid JSON: %.200s", text)
            raise AIUnavailable("bad_json") from None
