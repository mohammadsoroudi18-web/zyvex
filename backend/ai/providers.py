"""Provider layer.

UI -> AI Service -> Provider -> Model

Each provider is a thin, real HTTP client. Keys are never stored in the app
database; they are read from the process environment (delivered by the
platform's managed secret file).
"""
from __future__ import annotations

import os
from typing import Any

import httpx


class AIError(Exception):
    """Raised when a provider call cannot be completed."""


class BaseProvider:
    id = "base"
    label = "Base"
    env_key: str | None = None
    default_model = ""
    default_base_url = ""
    requires_key = True

    def __init__(self, settings: dict):
        self.settings = settings

    # -- configuration ----------------------------------------------------- #
    def api_key(self) -> str | None:
        return os.environ.get(self.env_key) if self.env_key else None

    def base_url(self) -> str:
        return (self.settings.get("base_url") or self.default_base_url).rstrip("/")

    def model(self) -> str:
        return self.settings.get("model") or self.default_model

    def available(self) -> bool:
        if self.requires_key and not self.api_key():
            return False
        return bool(self.base_url())

    def unavailable_reason(self) -> str:
        if self.requires_key and not self.api_key():
            return f"{self.env_key} is not configured"
        return "provider is not reachable"

    # -- generation -------------------------------------------------------- #
    def complete(self, *, system: str, messages: list[dict], max_tokens: int,
                 temperature: float) -> dict:
        raise NotImplementedError

    # -- helpers ----------------------------------------------------------- #
    def _post(self, url: str, *, headers: dict, payload: dict, timeout: float = 120) -> dict:
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
        except httpx.HTTPError as exc:
            raise AIError(f"network error contacting {self.label}: {exc}") from exc
        if response.status_code >= 400:
            raise AIError(f"{self.label} returned HTTP {response.status_code}: {response.text[:400]}")
        try:
            return response.json()
        except ValueError as exc:
            raise AIError(f"{self.label} returned a non-JSON response") from exc


class AnthropicProvider(BaseProvider):
    id = "anthropic"
    label = "Anthropic"
    env_key = "ANTHROPIC_API_KEY"
    default_model = "claude-sonnet-4-5"
    default_base_url = "https://api.anthropic.com"

    def complete(self, *, system, messages, max_tokens, temperature):
        payload = {
            "model": self.model(),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
        }
        data = self._post(
            f"{self.base_url()}/v1/messages",
            headers={
                "x-api-key": self.api_key() or "",
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            payload=payload,
        )
        text = "".join(block.get("text", "") for block in data.get("content", []))
        return {"text": text, "usage": data.get("usage", {}), "model": data.get("model", self.model())}


class OpenAIProvider(BaseProvider):
    id = "openai"
    label = "OpenAI"
    env_key = "OPENAI_API_KEY"
    default_model = "gpt-4o-mini"
    default_base_url = "https://api.openai.com"

    def complete(self, *, system, messages, max_tokens, temperature):
        payload = {
            "model": self.model(),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        data = self._post(
            f"{self.base_url()}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key()}", "content-type": "application/json"},
            payload=payload,
        )
        choices = data.get("choices") or [{}]
        return {
            "text": (choices[0].get("message") or {}).get("content", ""),
            "usage": data.get("usage", {}),
            "model": data.get("model", self.model()),
        }


class OpenAICompatibleProvider(OpenAIProvider):
    id = "openai_compatible"
    label = "OpenAI-compatible"
    env_key = "OPENAI_COMPATIBLE_API_KEY"
    default_model = ""
    default_base_url = os.environ.get("OPENAI_COMPATIBLE_BASE_URL", "http://localhost:8080")

    def base_url(self) -> str:
        return (self.settings.get("base_url")
                or os.environ.get("OPENAI_COMPATIBLE_BASE_URL")
                or self.default_base_url).rstrip("/")


class OpenRouterProvider(OpenAIProvider):
    id = "openrouter"
    label = "OpenRouter"
    env_key = "OPENROUTER_API_KEY"
    default_model = "anthropic/claude-3.5-sonnet"
    default_base_url = "https://openrouter.ai/api"

    def complete(self, *, system, messages, max_tokens, temperature):
        payload = {
            "model": self.model(),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        data = self._post(
            f"{self.base_url()}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key()}",
                "content-type": "application/json",
                "HTTP-Referer": "https://nexora.local",
                "X-Title": "NEXORA AI Builder",
            },
            payload=payload,
        )
        choices = data.get("choices") or [{}]
        return {
            "text": (choices[0].get("message") or {}).get("content", ""),
            "usage": data.get("usage", {}),
            "model": data.get("model", self.model()),
        }


class OllamaProvider(BaseProvider):
    id = "ollama"
    label = "Ollama"
    env_key = None
    requires_key = False
    default_model = "llama3.1"
    default_base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    def base_url(self) -> str:
        return (self.settings.get("base_url")
                or os.environ.get("OLLAMA_BASE_URL")
                or self.default_base_url).rstrip("/")

    def available(self) -> bool:
        return bool(self.base_url())

    def complete(self, *, system, messages, max_tokens, temperature):
        payload = {
            "model": self.model(),
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "messages": [{"role": "system", "content": system}, *messages],
        }
        data = self._post(f"{self.base_url()}/api/chat", headers={"content-type": "application/json"},
                          payload=payload)
        message = data.get("message") or {}
        return {"text": message.get("content", ""), "usage": {}, "model": data.get("model", self.model())}


PROVIDERS: dict[str, type[BaseProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "openai_compatible": OpenAICompatibleProvider,
    "openrouter": OpenRouterProvider,
    "ollama": OllamaProvider,
}


def get_provider(settings: dict) -> BaseProvider:
    provider_id = settings.get("provider", "anthropic")
    provider_cls = PROVIDERS.get(provider_id, AnthropicProvider)
    return provider_cls(settings)


def provider_catalog(settings: dict) -> list[dict[str, Any]]:
    """Describe every supported provider for the Settings UI (never exposes keys)."""
    catalog = []
    for provider_id, provider_cls in PROVIDERS.items():
        instance = provider_cls(settings)
        catalog.append(
            {
                "id": provider_id,
                "label": provider_cls.label,
                "env_key": provider_cls.env_key,
                "requires_key": provider_cls.requires_key,
                "key_present": bool(instance.api_key()) if provider_cls.env_key else True,
                "available": instance.available(),
                "default_model": provider_cls.default_model,
                "default_base_url": instance.base_url(),
                "unavailable_reason": None if instance.available() else instance.unavailable_reason(),
            }
        )
    return catalog
