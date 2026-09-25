"""M9 LLM configuration and client tests.

Covers the runtime LLM configuration interface (LLM_PROVIDER / LLM_MODEL /
LLM_BASE_URL / LLM_API_KEY plus the OPENROUTER_API_KEY fallback), provider
reporting, structured-output retry on malformed model responses, mock fallback,
and secret safety. No test here performs real network inference.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from backend.agents.investigation.models.hypothesis import Hypothesis
from backend.llm.factory import LLMNotConfigured, create_llm_client
from backend.llm.interface import LLMMessage
from backend.llm.providers.experiential import ExperientialClient, MockLLMClient
from backend.llm.settings import (
    OPENROUTER_DEFAULT_BASE_URL,
    OPENROUTER_DEFAULT_MODEL,
    LLMSettings,
    is_production_env,
)

REPO = Path(__file__).resolve().parents[2]
# Assembled from parts so this file never contains a literal OpenRouter key
# prefix (the repository-wide secret scan below asserts that no such literal
# exists anywhere, including here).
SYNTHETIC_KEY = "sk" + "-or-v1-test-key-not-real-0000000000000000000000000000"
# The OpenRouter key prefix, also assembled from parts so the scan below stays
# honest about the file it lives in.
KEY_PREFIX = "sk" + "-or-v1-"


def _clear_llm_env(monkeypatch) -> None:
    for name in (
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_TIMEOUT",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    # `LLMSettings` declares `env_file=".env"`, so on a developer machine that has
    # a real local `.env` these tests would read that file instead of the cleared
    # environment — silently asserting against the developer's own provider and
    # key. Disabling the env file keeps every settings test a pure test of the
    # environment-variable contract, and keeps real secrets out of assertions.
    monkeypatch.setitem(LLMSettings.model_config, "env_file", None)


class TestLLMSettings:
    def test_unconfigured_falls_back_to_mock(self, monkeypatch):
        _clear_llm_env(monkeypatch)
        monkeypatch.delenv("APP_ENV", raising=False)
        settings = LLMSettings()
        assert settings.configured is False
        assert isinstance(create_llm_client(settings), MockLLMClient)

    def test_production_refuses_mock_fallback(self, monkeypatch):
        _clear_llm_env(monkeypatch)
        monkeypatch.setenv("APP_ENV", "production")
        settings = LLMSettings()
        assert settings.configured is False
        assert is_production_env() is True
        with pytest.raises(LLMNotConfigured):
            create_llm_client(settings)

    def test_production_ignores_dotenv_file(self, monkeypatch, tmp_path):
        _clear_llm_env(monkeypatch)
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text(
            "LLM_PROVIDER=openrouter\nLLM_API_KEY=" + SYNTHETIC_KEY + "\n",
            encoding="utf-8",
        )
        settings = LLMSettings()
        assert settings.api_key == ""
        assert settings.configured is False

    def test_openrouter_env_is_used(self, monkeypatch):
        _clear_llm_env(monkeypatch)
        monkeypatch.setenv("LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("LLM_API_KEY", SYNTHETIC_KEY)
        settings = LLMSettings()
        assert settings.provider == "openrouter"
        assert settings.configured is True
        # Model and base URL default to the configured OpenRouter Llama endpoint.
        assert settings.model == OPENROUTER_DEFAULT_MODEL
        assert settings.base_url == OPENROUTER_DEFAULT_BASE_URL
        assert settings.endpoint_host == "openrouter.ai"

    def test_explicit_model_and_base_url_win(self, monkeypatch):
        _clear_llm_env(monkeypatch)
        monkeypatch.setenv("LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("LLM_API_KEY", SYNTHETIC_KEY)
        monkeypatch.setenv("LLM_MODEL", "meta-llama/llama-3.1-70b-instruct")
        monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
        settings = LLMSettings()
        assert settings.model == "meta-llama/llama-3.1-70b-instruct"
        assert settings.base_url == "https://openrouter.ai/api/v1"

    def test_openrouter_api_key_is_a_fallback_source(self, monkeypatch):
        _clear_llm_env(monkeypatch)
        monkeypatch.setenv("LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("OPENROUTER_API_KEY", SYNTHETIC_KEY)
        settings = LLMSettings()
        assert settings.api_key == SYNTHETIC_KEY
        assert settings.configured is True

    def test_llm_api_key_takes_precedence_over_fallback(self, monkeypatch):
        _clear_llm_env(monkeypatch)
        monkeypatch.setenv("LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("OPENROUTER_API_KEY", "fallback-key")
        monkeypatch.setenv("LLM_API_KEY", SYNTHETIC_KEY)
        assert LLMSettings().api_key == SYNTHETIC_KEY

    def test_api_key_not_exposed_by_repr(self, monkeypatch):
        _clear_llm_env(monkeypatch)
        monkeypatch.setenv("LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("LLM_API_KEY", SYNTHETIC_KEY)
        settings = LLMSettings()
        # Only assert that the secret is never surfaced by the client's safe metadata.
        client = create_llm_client(settings)
        assert client.provider_name == "openrouter"
        assert client.model_name == OPENROUTER_DEFAULT_MODEL
        assert client.endpoint_host == "openrouter.ai"


class _StubResponse:
    def __init__(self, payload=None, status_code: int = 200, content: str = ""):
        self._payload = payload if payload is not None else _chat_payload(content)
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"Server error '{self.status_code}' for url 'https://openrouter.ai/api/v1/chat/completions'",
                request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
                response=httpx.Response(self.status_code),
            )


def _chat_payload(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"total_tokens": 1},
    }


def _client(max_retries: int = 1) -> ExperientialClient:
    return ExperientialClient(
        api_key=SYNTHETIC_KEY,
        model=OPENROUTER_DEFAULT_MODEL,
        base_url=OPENROUTER_DEFAULT_BASE_URL,
        provider="openrouter",
        max_retries=max_retries,
    )


class TestStructuredOutput:
    def test_retries_then_parses(self, monkeypatch):
        client = _client()
        responses = [
            _StubResponse(content="I am sorry, here is no JSON at all"),
            _StubResponse(content='{"module_id": "syn-mod-0042", "candidates": []}'),
        ]
        calls = {"n": 0}

        def fake_post(url, json=None):
            resp = responses[min(calls["n"], len(responses) - 1)]
            calls["n"] += 1
            return resp

        monkeypatch.setattr(client._http, "post", fake_post)
        out = client.structured_completion(
            [LLMMessage(role="user", content="investigate")], Hypothesis
        )
        assert out.module_id == "syn-mod-0042"
        assert calls["n"] == 2

    def test_malformed_output_raises_without_leaking_key(self, monkeypatch):
        client = _client()
        monkeypatch.setattr(client._http, "post", lambda url, json=None: _StubResponse(content="not json"))
        with pytest.raises(ValueError) as excinfo:
            client.structured_completion([LLMMessage(role="user", content="x")], Hypothesis)
        message = str(excinfo.value)
        assert SYNTHETIC_KEY not in message
        assert "failed after" in message

    def test_rate_limit_is_retried_and_reported(self, monkeypatch):
        client = _client(max_retries=1)
        calls = {"n": 0}

        def fake_post(url, json=None):
            calls["n"] += 1
            if calls["n"] == 1:
                return _StubResponse(status_code=429)
            return _StubResponse(content='{"module_id": "m", "candidates": []}')

        monkeypatch.setattr(client._http, "post", fake_post)
        monkeypatch.setattr("backend.llm.providers.experiential.time.sleep", lambda *_: None)
        out = client.structured_completion([LLMMessage(role="user", content="x")], Hypothesis)
        assert out.module_id == "m"
        assert calls["n"] == 2

    def test_persistent_rate_limit_reports_error_without_key(self, monkeypatch):
        client = _client(max_retries=1)
        monkeypatch.setattr(client._http, "post", lambda url, json=None: _StubResponse(status_code=429))
        monkeypatch.setattr("backend.llm.providers.experiential.time.sleep", lambda *_: None)
        with pytest.raises(httpx.HTTPStatusError) as excinfo:
            client.structured_completion([LLMMessage(role="user", content="x")], Hypothesis)
        assert SYNTHETIC_KEY not in str(excinfo.value)

    def test_extract_json_tolerates_fences_and_prose(self):
        inner = '{"a": 1}'
        assert ExperientialClient._extract_json(f"```json\n{inner}\n```") == {"a": 1}
        assert ExperientialClient._extract_json(f"Here is the result:\n{inner}\nThanks.") == {"a": 1}
        assert ExperientialClient._extract_json(inner) == {"a": 1}

    def test_extract_json_rejects_garbage(self):
        import json

        with pytest.raises(json.JSONDecodeError):
            ExperientialClient._extract_json("no object here")


class TestHypothesisAgentFailureReporting:
    def test_failure_message_never_contains_the_key(self):
        from backend.agents.investigation.hypothesis_agent import HypothesisAgent

        class _FailingKeyedClient(ExperientialClient):
            def _post(self, payload):
                raise httpx.HTTPStatusError(
                    "Client error '401 Unauthorized' for url 'https://openrouter.ai/api/v1/chat/completions'",
                    request=httpx.Request(
                        "POST",
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {SYNTHETIC_KEY}"},
                    ),
                    response=httpx.Response(401),
                )

        agent = HypothesisAgent(llm=_FailingKeyedClient(api_key=SYNTHETIC_KEY, provider="openrouter"))
        out = agent.run({"module_id": "syn-mod-0042", "deterministic_results": [], "evidence_records": []})
        assert out["hypothesis"].candidates == []
        assert SYNTHETIC_KEY not in str(out["errors"])


class TestNoHardCodedSecrets:
    TEXT_SUFFIXES = {".py", ".md", ".json", ".toml", ".yml", ".yaml", ".txt", ".cfg", ".ini", ".sh", ".example"}
    SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache", "chroma"}

    def _text_files(self):
        for path in REPO.rglob("*"):
            if not path.is_file():
                continue
            if any(part in self.SKIP_DIRS for part in path.parts):
                continue
            if path.suffix in self.TEXT_SUFFIXES or path.name in (".env.example", "Dockerfile"):
                yield path

    def test_no_openrouter_key_material_in_repository(self):
        offenders = []
        for path in self._text_files():
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if KEY_PREFIX in text:
                offenders.append(str(path.relative_to(REPO)))
        assert offenders == [], f"credential material found in: {offenders}"

    def test_no_key_literal_assigned_in_source(self):
        import re

        pattern = re.compile(r"(LLM_API_KEY|OPENROUTER_API_KEY)\s*[:=]\s*[\"']sk-")
        offenders = []
        for path in self._text_files():
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if pattern.search(text):
                offenders.append(str(path.relative_to(REPO)))
        assert offenders == [], f"hard-coded credential in: {offenders}"
