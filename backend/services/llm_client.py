"""Provider-agnostic LLM client.

Select the provider with LLM_PROVIDER and the model with LLM_MODEL.
Each provider SDK is imported lazily, so only the configured provider's
package and API key are required. Currently implemented: gemini.
OpenAI / Anthropic slots are stubbed for future addition.
"""

import os
from typing import Optional

from anyio.to_thread import run_sync
from functools import partial

_DEFAULT_MODELS = {
    "gemini": "gemini-3.1-flash-lite",
    # Cheapest / smallest default models per provider (future)
    "openai": "gpt-5-mini",
    "anthropic": "claude-haiku-4-5",
}

_PROVIDER_KEY_ENV = {
    "gemini": "GOOGLE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


class LLMClient:
    """Single-method client: send a prompt, get raw text (JSON expected) back.

    Token-frugal by default: temperature 0 and small max_output_tokens.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        max_output_tokens: int = 512,
    ):
        self.provider = (
            provider or os.getenv("LLM_PROVIDER") or "gemini"
        ).strip().lower()
        self.model = (
            model
            or os.getenv("LLM_MODEL")
            or os.getenv("GEMINI_MODEL")  # backward compat
            or _DEFAULT_MODELS.get(self.provider, "")
        )
        key_env = _PROVIDER_KEY_ENV.get(self.provider, "GOOGLE_API_KEY")
        self.api_key = api_key or os.getenv(key_env)
        self.max_output_tokens = max_output_tokens
        self._client = None
        self._available: Optional[bool] = None

    def _check_available(self) -> bool:
        if self._available is not None:
            return self._available
        if not self.api_key:
            print(
                f"[LLMClient] No API key for provider '{self.provider}' "
                f"(expected env var), LLM disabled"
            )
            self._available = False
            return False
        try:
            if self.provider == "gemini":
                import google.genai  # noqa: F401
            elif self.provider in ("openai", "anthropic"):
                print(
                    f"[LLMClient] Provider '{self.provider}' is not implemented yet, "
                    "LLM disabled"
                )
                self._available = False
                return False
            else:
                print(f"[LLMClient] Unknown provider '{self.provider}', LLM disabled")
                self._available = False
                return False
            self._available = True
            return True
        except ImportError:
            print(
                f"[LLMClient] SDK for provider '{self.provider}' not installed, "
                "LLM disabled"
            )
            self._available = False
            return False

    def _get_client(self):
        if self._client is None:
            if self.provider == "gemini":
                from google.genai import Client

                self._client = Client(api_key=self.api_key)
            else:
                raise NotImplementedError(
                    f"Provider '{self.provider}' is not implemented yet"
                )
        return self._client

    async def generate_json(self, prompt: str) -> Optional[str]:
        """Send a compact prompt, return raw text response (expected JSON) or None."""
        if not self._check_available():
            return None
        try:
            client = self._get_client()
            if self.provider == "gemini":
                response = await run_sync(
                    partial(
                        client.models.generate_content,
                        model=self.model,
                        contents=prompt,
                        config={
                            "temperature": 0.0,
                            "max_output_tokens": self.max_output_tokens,
                        },
                    ),
                )
                return response.text
            raise NotImplementedError(
                f"Provider '{self.provider}' is not implemented yet"
            )
        except Exception as e:
            print(f"[LLMClient] LLM call failed ({self.provider}/{self.model}): {e}")
            return None


_shared_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """FastAPI dependency: one shared client per process."""
    global _shared_client
    if _shared_client is None:
        _shared_client = LLMClient()
    return _shared_client
