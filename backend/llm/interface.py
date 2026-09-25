from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMMessage(BaseModel):
    role: str
    content: str


class LLMResponse(BaseModel):
    content: str
    finish_reason: str = ""
    usage: Optional[dict] = None


class LLMClient(ABC):
    @abstractmethod
    def chat_completion(
        self,
        messages: List[LLMMessage],
        system: str = "",
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> LLMResponse: ...

    @abstractmethod
    def structured_completion(
        self,
        messages: List[LLMMessage],
        response_model: Type[T],
        system: str = "",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        retries: int = 2,
    ) -> T: ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...