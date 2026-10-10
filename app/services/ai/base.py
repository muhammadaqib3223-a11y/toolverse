"""The AI provider interface. Every tool talks to AI only through this, never to a vendor SDK.

To add a provider (e.g. OpenAI): write a class with the same methods in its own file, add it to
PROVIDERS in app/services/ai/__init__.py, and set AI_PROVIDER in .env. No tool code changes.
"""
from abc import ABC, abstractmethod


class AIError(Exception):
    """Something went wrong with the AI. `code` is one of the codes below; tools turn it into
    friendly, translated text. The vendor's own error is logged, never shown to users."""

    code = "ai_unavailable"

    def __init__(self, detail=""):
        super().__init__(detail or self.code)


class AIUnavailable(AIError):
    """Not configured, network trouble, the vendor is down or it sent back something unusable."""

    code = "ai_unavailable"


class AIQuotaExceeded(AIError):
    """The vendor's rate limit or free quota is used up for now."""

    code = "ai_quota"


class AIBlocked(AIError):
    """The vendor refused to answer, usually because of its safety filters."""

    code = "ai_blocked"


class AIProvider(ABC):
    name = "base"

    @classmethod
    @abstractmethod
    def from_config(cls, config):
        """Build the provider from the Flask config (API key, model, timeout)."""

    @abstractmethod
    def generate_json(self, *, system, prompt, schema, temperature=0.9, max_output_tokens=2048):
        """Ask the model for JSON matching `schema` (JSON Schema) and return it parsed.

        `system` = instructions; `prompt` = the user's request. Raises an AIError subclass on failure.
        """
