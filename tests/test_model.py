"""Tests for the OpenAI-compatible model client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from testproof.model import ModelClient, ModelConfig


def test_model_config_defaults() -> None:
    config = ModelConfig(api_key="test-key")
    assert config.base_url == "https://openrouter.ai/api/v1"
    assert config.model == "qwen/qwen3-235b-a22b-2507"
    assert config.max_tokens == 1200
    assert config.temperature == 0.0


def test_complete_returns_content() -> None:
    config = ModelConfig(api_key="test-key")
    client = ModelClient(config)

    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "def test_x(): pass"}}]}
    mock_response.raise_for_status = MagicMock()

    with patch.object(client._client, "post", return_value=mock_response):
        result = client.complete("write a test")
        assert result == "def test_x(): pass"


def test_complete_raises_on_no_choices() -> None:
    config = ModelConfig(api_key="test-key")
    client = ModelClient(config)

    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": []}
    mock_response.raise_for_status = MagicMock()

    with (
        patch.object(client._client, "post", return_value=mock_response),
        pytest.raises(RuntimeError, match="no choices"),
    ):
        client.complete("write a test")


def test_complete_raises_on_empty_content() -> None:
    config = ModelConfig(api_key="test-key")
    client = ModelClient(config)

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "", "reasoning": "thinking"}}]
    }
    mock_response.raise_for_status = MagicMock()

    with (
        patch.object(client._client, "post", return_value=mock_response),
        pytest.raises(RuntimeError, match="empty content"),
    ):
        client.complete("write a test")


def test_from_env_requires_api_key(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="MODEL_API_KEY"):
        ModelClient.from_env()


def test_from_env_uses_env_vars(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MODEL_API_KEY", "env-key")
    monkeypatch.setenv("MODEL_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("MODEL_NAME", "test-model")
    monkeypatch.setenv("MODEL_MAX_TOKENS", "900")
    client = ModelClient.from_env()
    assert client._config.api_key == "env-key"
    assert client._config.base_url == "https://example.com/v1"
    assert client._config.model == "test-model"
    assert client._config.max_tokens == 900
    client.close()


def test_from_env_model_override_wins(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MODEL_API_KEY", "env-key")
    monkeypatch.setenv("MODEL_NAME", "configured-model")
    client = ModelClient.from_env(model_override="override-model")
    assert client.model_name == "override-model"
    client.close()


def test_close() -> None:
    config = ModelConfig(api_key="test-key")
    client = ModelClient(config)
    client.close()
    # Should not raise
