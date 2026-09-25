from __future__ import annotations

from backend.llm.interface import LLMClient
from backend.llm.providers.experiential import ExperientialClient, MockLLMClient
from backend.llm.settings import LLMSettings, is_production_env


class LLMNotConfigured(RuntimeError):
    """Production was asked to reason without a configured provider."""


def create_llm_client(settings: LLMSettings | None = None) -> LLMClient:
    """Create the configured LLM client.

    Development and test still fall back to ``MockLLMClient`` when no provider
    is configured, so existing unit tests keep a deterministic hypothesis path.
    A production process (``APP_ENV=production``) refuses that fallback: a
    missing credential is a failed deployment, not a silent mock investigation.
    """
    if settings is None:
        settings = LLMSettings()
    if settings.configured:
        return ExperientialClient(
            api_key=settings.api_key,
            model=settings.model,
            base_url=settings.base_url,
            timeout=settings.timeout,
            provider=settings.provider,
        )
    if is_production_env():
        raise LLMNotConfigured(
            "LLM provider is not configured. Set the provider and credential "
            "in the deployment environment. Production does not fall back to mock inference."
        )
    return MockLLMClient()


def create_mock_client() -> MockLLMClient:
    return MockLLMClient()
