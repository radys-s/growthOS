"""LLM provider abstraction.

Implementations extract structured data from text. They never produce the final
ranking score (ADR 0003), and whatever they return is verified by code before use (ADR 0006).
"""

from typing import TYPE_CHECKING, Protocol, TypeVar

import httpx
from pydantic import BaseModel

if TYPE_CHECKING:
    from app.config import Settings

T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    name: str

    def extract(self, text: str, schema: type[T], instructions: str) -> T:
        """Return ``schema`` filled from ``text``. Unknown fields must stay None.
        Raises ``ProviderError`` when the model cannot be reached or answers garbage."""
        ...


class ProviderError(RuntimeError):
    pass


class ProviderNotConfiguredError(ProviderError):
    pass


def get_provider(settings: "Settings", client: httpx.Client) -> LLMProvider | None:
    """The configured provider, or None when LLM_BASE_URL is empty."""
    if not settings.llm_base_url.strip():
        return None
    from app.ai.openai_compat import OpenAICompatProvider

    return OpenAICompatProvider(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        client=client,
    )
