"""OpenAI-compatible model client for verified repair."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for the model client."""

    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "meta-llama/llama-3.1-8b-instruct"
    max_tokens: int = 500
    temperature: float = 0.0


class ModelClient:
    """Thin wrapper around the OpenAI chat completions API.

    Works with any OpenAI-compatible provider: OpenRouter, Together AI,
    Fireworks, Groq, Ollama, or any self-hosted model.
    """

    def __init__(self, config: ModelConfig) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )

    def complete(self, prompt: str, *, max_tokens: int | None = None) -> str:
        """Send a prompt and return the model's response text."""
        tokens = max_tokens if max_tokens is not None else self._config.max_tokens
        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": tokens,
            "temperature": self._config.temperature,
        }
        response = self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            msg = "Model returned no choices"
            raise RuntimeError(msg)
        content = choices[0].get("message", {}).get("content", "")
        return str(content).strip()

    def close(self) -> None:
        self._client.close()

    @classmethod
    def from_env(cls) -> ModelClient:
        """Create a client from environment variables."""
        api_key = os.environ.get("MODEL_API_KEY", "")
        if not api_key:
            msg = "MODEL_API_KEY environment variable is required"
            raise RuntimeError(msg)
        base_url = os.environ.get("MODEL_BASE_URL", "https://openrouter.ai/api/v1")
        model = os.environ.get("MODEL_NAME", "meta-llama/llama-3.1-8b-instruct")
        config = ModelConfig(api_key=api_key, base_url=base_url, model=model)
        return cls(config)
