"""HTTP providers for OpenAI-compatible and Anthropic chat APIs (stdlib only)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from recoverypilot.llm.base import LLMError, LLMProvider


def _post_json(url: str, headers: dict[str, str], body: dict[str, Any], timeout: float) -> Any:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise LLMError(f"LLM API returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise LLMError(f"LLM API request failed: {exc}") from exc


def _api_key(env_var: str) -> str:
    key = os.environ.get(env_var, "").strip()
    if not key:
        raise LLMError(f"Environment variable {env_var} is not set; cannot call the LLM API")
    return key


class OpenAICompatibleProvider(LLMProvider):
    """Any ``/v1/chat/completions`` endpoint: OpenAI, Azure OpenAI gateways, Ollama, vLLM..."""

    name = "openai"

    def __init__(
        self, model: str, api_key_env: str, base_url: str | None = None, timeout: float = 30.0
    ) -> None:
        self.model = model
        self.api_key_env = api_key_env
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.timeout = timeout

    def complete(self, system: str, user: str) -> str:
        data = _post_json(
            f"{self.base_url}/chat/completions",
            {"Authorization": f"Bearer {_api_key(self.api_key_env)}"},
            {
                "model": self.model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            self.timeout,
        )
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Unexpected response shape from chat completions API") from exc


class AnthropicProvider(LLMProvider):
    """Anthropic Messages API."""

    name = "anthropic"

    def __init__(
        self, model: str, api_key_env: str, base_url: str | None = None, timeout: float = 30.0
    ) -> None:
        self.model = model
        self.api_key_env = api_key_env
        self.base_url = (base_url or "https://api.anthropic.com").rstrip("/")
        self.timeout = timeout

    def complete(self, system: str, user: str) -> str:
        data = _post_json(
            f"{self.base_url}/v1/messages",
            {"x-api-key": _api_key(self.api_key_env), "anthropic-version": "2023-06-01"},
            {
                "model": self.model,
                "max_tokens": 1024,
                "temperature": 0.2,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            self.timeout,
        )
        try:
            return "".join(
                block.get("text", "") for block in data["content"] if block.get("type") == "text"
            )
        except (KeyError, TypeError) as exc:
            raise LLMError("Unexpected response shape from Anthropic Messages API") from exc
