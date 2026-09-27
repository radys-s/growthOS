"""OpenAI-compatible chat completions provider (OmniRoute, Ollama, LM Studio, OpenAI, …)."""

import json
import re
from typing import TypeVar

import httpx
from pydantic import BaseModel

from app.ai.provider import ProviderError

T = TypeVar("T", bound=BaseModel)

LLM_TIMEOUT = httpx.Timeout(90.0, connect=5.0)  # free models can be slow
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def _json_object(content: str) -> str:
    text = _FENCE.sub("", content.strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ProviderError("model answer contains no JSON object")
    return text[start : end + 1]


class OpenAICompatProvider:
    name = "openai_compat"

    def __init__(self, base_url: str, api_key: str, model: str, client: httpx.Client) -> None:
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key.strip()
        self.model = model
        self.client = client

    def _post(self, payload: dict) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        return self.client.post(self.url, json=payload, headers=headers, timeout=LLM_TIMEOUT)

    def extract(self, text: str, schema: type[T], instructions: str) -> T:
        system = (
            f"{instructions}\n\nAnswer with ONE JSON object and nothing else. It must match this "
            f"JSON schema:\n{json.dumps(schema.model_json_schema(), ensure_ascii=False)}\n"
            "Use null for anything the text does not state explicitly. Never guess."
        )
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": text}],
            "response_format": {"type": "json_object"},
        }
        try:
            response = self._post(payload)
            if response.status_code in (400, 422):  # some backends reject response_format
                payload.pop("response_format")
                response = self._post(payload)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"] or ""
            return schema.model_validate_json(_json_object(content))
        except ProviderError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            # ValidationError and JSONDecodeError are ValueErrors
            raise ProviderError(f"{type(exc).__name__}: {exc}"[:300]) from exc
