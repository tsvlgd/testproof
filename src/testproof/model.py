"""OpenAI-compatible model client for verified repair."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for the model client."""

    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "qwen/qwen-2.5-coder-32b-instruct"
    max_tokens: int = 500
    temperature: float = 0.0

    @classmethod
    def from_file(cls, path: Path) -> ModelConfig:
        """Load config from a JSON file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            api_key=data.get("api_key", ""),
            base_url=data.get("base_url", "https://openrouter.ai/api/v1"),
            model=data.get("model", "qwen/qwen-2.5-coder-32b-instruct"),
            max_tokens=data.get("max_tokens", 500),
            temperature=data.get("temperature", 0.0),
        )


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
        """Create a client from environment variables or a config file.

        Checks in order:
        1. MODEL_API_KEY environment variable
        2. ~/.config/testproof/model.json
        3. .testproof/model.json in the current directory
        """
        api_key = os.environ.get("MODEL_API_KEY", "")
        base_url = os.environ.get("MODEL_BASE_URL", "")
        model = os.environ.get("MODEL_NAME", "")

        if not api_key:
            config_paths = [
                Path.home() / ".config" / "testproof" / "model.json",
                Path(".testproof") / "model.json",
            ]
            for config_path in config_paths:
                if config_path.exists():
                    config = ModelConfig.from_file(config_path)
                    if config.api_key:
                        return cls(config)

        if not api_key:
            msg = (
                "MODEL_API_KEY environment variable is required, or create "
                "~/.config/testproof/model.json with "
                '{\\"api_key\\": \\"...\\", \\"base_url\\": \\"...\\", \\"model\\": \\"...\\"}'
            )
            raise RuntimeError(msg)

        config = ModelConfig(
            api_key=api_key,
            base_url=base_url or "https://openrouter.ai/api/v1",
            model=model or "qwen/qwen-2.5-coder-32b-instruct",
        )
        return cls(config)
