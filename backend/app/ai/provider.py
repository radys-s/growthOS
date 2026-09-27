"""LLM provider abstraction (no provider is wired in Milestone 0/1).

Implementations extract structured data from text. They never produce the final
ranking score (ADR 0003).
"""

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    name: str

    def extract(self, text: str, schema: type[T], instructions: str) -> T:
        """Return ``schema`` filled from ``text``. Unknown fields must stay None."""
        ...


class ProviderNotConfiguredError(RuntimeError):
    pass


def get_provider(name: str) -> LLMProvider:
    raise ProviderNotConfiguredError(f"AI provider '{name}' is not configured yet")
