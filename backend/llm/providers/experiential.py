from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from backend.llm.interface import LLMClient, LLMMessage, LLMResponse

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct"
DEFAULT_BASE_URL = "https://api.experiential.ai/v1/"
# Transient conditions worth retrying: rate limits and upstream/server errors.
RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504, 529}


class ExperientialClient(LLMClient):
    """OpenAI-compatible chat-completions client.

    Works against any OpenAI-compatible endpoint (OpenRouter included) by
    pointing ``base_url`` at the provider root, e.g.
    ``https://openrouter.ai/api/v1``. The provider name is carried through to
    reporting so a run is never mislabelled. The API key is held in memory only:
    it is never logged, serialized, or included in error messages.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "",
        base_url: str = "",
        timeout: float = 120.0,
        provider: str = "experiential",
        max_retries: int = 2,
    ):
        self._api_key = api_key
        self._provider = provider or "experiential"
        self._model = model or DEFAULT_MODEL
        self._base_url = (base_url.rstrip("/") + "/") if base_url else DEFAULT_BASE_URL
        self._timeout = timeout
        self._max_retries = max(0, int(max_retries))
        self._http = httpx.Client(timeout=timeout, headers=self._headers())

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    @property
    def provider_name(self) -> str:
        return self._provider

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def endpoint_host(self) -> str:
        """Endpoint host only — safe to display and log."""
        return httpx.URL(self._base_url).host or ""

    def _post(self, payload: dict) -> dict:
        url = f"{self._base_url}chat/completions"
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._http.post(url, json=payload)
            except httpx.TransportError:
                if attempt < self._max_retries:
                    time.sleep(min(2.0 * (attempt + 1), 8.0))
                    continue
                raise
            if resp.status_code in RETRYABLE_STATUS_CODES and attempt < self._max_retries:
                time.sleep(min(2.0 * (attempt + 1), 8.0))
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError("unreachable")  # pragma: no cover

    def chat_completion(
        self,
        messages: List[LLMMessage],
        system: str = "",
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        msgs = [{"role": "system", "content": system}] if system else []
        msgs += [{"role": m.role, "content": m.content} for m in messages]
        payload: dict = {
            "model": self._model,
            "messages": msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = self._post(payload)
        choice = data["choices"][0]
        return LLMResponse(
            content=choice["message"]["content"] or "",
            finish_reason=choice.get("finish_reason", ""),
            usage=data.get("usage"),
        )

    def structured_completion(
        self,
        messages: List[LLMMessage],
        response_model: Type[T],
        system: str = "",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        retries: int = 2,
    ) -> T:
        schema_json = response_model.model_json_schema()
        instruction = "Respond only with valid JSON matching this schema:\n" + json.dumps(schema_json, indent=2)
        sys_msg = system + "\n\n" + instruction if system else instruction

        last_error: Optional[str] = None
        for attempt in range(1 + retries):
            try:
                msgs = [{"role": "system", "content": sys_msg}]
                if last_error:
                    msgs.append({
                        "role": "system",
                        "content": (
                            "Previous attempt failed JSON/Pydantic validation. "
                            f"Error: {last_error}. Respond with valid JSON only, with no prose and no code fences."
                        ),
                    })
                msgs += [{"role": m.role, "content": m.content} for m in messages]
                payload: dict = {
                    "model": self._model,
                    "messages": msgs,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                data = self._post(payload)
                content = data["choices"][0]["message"]["content"] or ""
                parsed = self._extract_json(content)
                return response_model.model_validate(parsed)
            except (ValidationError, json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
                last_error = str(e)
                continue
        raise ValueError(f"structured_completion failed after {1 + retries} attempts. Last error: {last_error}")

    @staticmethod
    def _extract_json(text: str) -> Any:
        text = text.strip()
        if text.startswith("```"):
            for delim in ("```json", "```JSON", "```"):
                if text.startswith(delim):
                    text = text[len(delim):]
                    if "```" in text:
                        text = text[: text.rindex("```")]
                    break
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Tolerate prose around the JSON object, which reasoning models
            # sometimes emit even when asked for JSON only.
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                return json.loads(text[start : end + 1])
            raise

    def close(self) -> None:
        self._http.close()


class MockLLMClient(LLMClient):
    def __init__(self, model: str = "mock"):
        self._model = model
        self._responses: List[Any] = []
        self._call_count = 0

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model

    def enqueue(self, response: Any) -> None:
        self._responses.append(response)

    def enqueue_many(self, responses: List[Any]) -> None:
        self._responses.extend(responses)

    @property
    def call_count(self) -> int:
        return self._call_count

    def chat_completion(
        self,
        messages: List[LLMMessage] = None,
        system: str = "",
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        self._call_count += 1
        if self._responses:
            r = self._responses.pop(0)
            if isinstance(r, str):
                return LLMResponse(content=r)
            if isinstance(r, dict) and "content" in r:
                return LLMResponse(**r)
            if isinstance(r, LLMResponse):
                return r
        return LLMResponse(content="[mock response]")

    def structured_completion(
        self,
        messages: List[LLMMessage] = None,
        response_model: Type[T] = None,
        system: str = "",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        retries: int = 2,
    ) -> T:
        self._call_count += 1
        if self._responses:
            r = self._responses.pop(0)
            if isinstance(r, dict):
                return response_model.model_validate(r)
            if isinstance(r, str):
                try:
                    return response_model.model_validate_json(r)
                except Exception:
                    pass
            if isinstance(r, BaseModel):
                return r
        if response_model is not None:
            try:
                return response_model.model_validate({})
            except Exception:
                pass
        return response_model.model_validate({"module_id": ""})
