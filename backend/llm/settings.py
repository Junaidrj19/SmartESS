from __future__ import annotations

import os

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

# The OpenRouter model used when the provider is OpenRouter and no explicit
# model was configured. Llama 3.3 70B Instruct is a currently available Meta
# instruction-following model on OpenRouter, verified against the live
# /v1/models catalogue, with a 131k context window and reliable JSON output for
# the structured hypothesis schema.
OPENROUTER_DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct"
OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_CHROMA_PATH = "knowledge_base/chroma"


def is_production_env() -> bool:
    """True when this process was started as a production deployment.

    Development and test keep the existing mock fallback. Production does not.
    """
    return os.environ.get("APP_ENV", "").strip().lower() in {"production", "prod"}


class LLMSettings(BaseSettings):
    """Runtime LLM configuration.

    Environment variables (unchanged interface):

    * ``LLM_PROVIDER`` — provider name, e.g. ``openrouter``
    * ``LLM_MODEL`` — model identifier
    * ``LLM_BASE_URL`` — OpenAI-compatible base URL, e.g. ``https://openrouter.ai/api/v1``
    * ``LLM_API_KEY`` — bearer token (never committed, never logged)
    * ``LLM_TIMEOUT`` — per-request timeout in seconds
    * ``LLM_EMBEDDING_MODEL`` / ``LLM_CHROMA_PATH`` — embeddings and vector store

    For convenience, ``OPENROUTER_API_KEY`` is honoured as a fallback source for
    the API key (and ``EMBEDDING_MODEL`` / ``CHROMA_PATH`` for the remaining
    fields) so an existing OpenRouter-only environment works without renaming
    anything. Values passed explicitly or via ``.env`` always win.
    """

    provider: str = ""
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    chroma_path: str = DEFAULT_CHROMA_PATH
    prompt_version: str = "m9-v1"
    timeout: float = 120.0

    # Fallback sources that are not prefixed with LLM_.
    openrouter_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    legacy_embedding_model: str = Field(default="", validation_alias="EMBEDDING_MODEL")
    legacy_chroma_path: str = Field(default="", validation_alias="CHROMA_PATH")

    @model_validator(mode="after")
    def _apply_fallbacks(self) -> "LLMSettings":
        if not self.api_key and self.openrouter_api_key:
            self.api_key = self.openrouter_api_key
        if self.provider.strip().lower() == "openrouter" and not self.api_key:
            self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if self.embedding_model in ("", DEFAULT_EMBEDDING_MODEL) and self.legacy_embedding_model:
            self.embedding_model = self.legacy_embedding_model
        if self.chroma_path in ("", DEFAULT_CHROMA_PATH) and self.legacy_chroma_path:
            self.chroma_path = self.legacy_chroma_path
        if self.provider.strip().lower() == "openrouter":
            if not self.base_url:
                self.base_url = OPENROUTER_DEFAULT_BASE_URL
            if not self.model:
                self.model = OPENROUTER_DEFAULT_MODEL
        return self

    @property
    def configured(self) -> bool:
        return bool(self.provider and self.api_key)

    @property
    def endpoint_host(self) -> str:
        """Host of the configured endpoint, safe to log."""
        from urllib.parse import urlparse

        return urlparse(self.base_url).netloc if self.base_url else ""

    model_config = {"env_prefix": "LLM_", "env_file": ".env", "extra": "ignore"}

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # Production credentials come from the deployment environment only.
        # A developer `.env` on disk must not be treated as a production secret.
        if is_production_env():
            return init_settings, env_settings, file_secret_settings
        return init_settings, env_settings, dotenv_settings, file_secret_settings
