"""AI service — turns UI intent into real provider calls.

Nothing here is hard-coded: every response comes from the configured provider.
When no provider is configured the service raises AIError so the UI can surface
an honest "AI not configured" state.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .providers import AIError, get_provider

ENHANCE_SYSTEM = """You are NEXORA's prompt architect for a professional software \
development workspace. Rewrite the user's rough request into a precise, buildable \
engineering specification. Be concrete about stack, structure, data model, UI, and \
acceptance criteria. Return only the improved specification as markdown."""

CHAT_SYSTEM = """You are NEXORA, an AI software engineering assistant inside a \
developer workspace. You help the user understand, plan, build, inspect, test and \
fix software. Be precise and technical. Use the provided project context. Never claim \
a build, test or preview succeeded unless the tool output you were given says so."""

PLAN_SYSTEM = """You are NEXORA's planning agent. Produce a structured, ordered build \
plan for the request. Return STRICT JSON only, shaped exactly as:
{"summary": "...", "tasks": [{"title": "...", "description": "...", "stage": "inspect|plan|execute|test|verify", "depends_on": [indexes]}]}
Do not include any prose outside the JSON."""

BUILD_SYSTEM = """You are NEXORA's coding agent. Given a request, plan and current \
project files, produce the file changes needed. Return STRICT JSON only, shaped as:
{"files": [{"path": "relative/path", "content": "full file content"}], "notes": "..."}
Only include files that must be created or changed. Do not include prose outside JSON."""


def _extract_json(text: str) -> Any:
    """Pull the first JSON object/array out of a model response."""
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    candidate = candidate.strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = candidate.find(opener)
        end = candidate.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(candidate[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise AIError("model did not return parseable JSON")


class AIService:
    def __init__(self, settings: dict):
        self.settings = settings
        self.provider = get_provider(settings)

    @property
    def available(self) -> bool:
        return self.provider.available()

    def _limits(self) -> tuple[int, float]:
        return (
            int(self.settings.get("max_tokens", 4096)),
            float(self.settings.get("temperature", 0.2)),
        )

    def _call(self, system: str, messages: list[dict]) -> dict:
        if not self.available:
            raise AIError(self.provider.unavailable_reason())
        max_tokens, temperature = self._limits()
        result = self.provider.complete(
            system=system, messages=messages, max_tokens=max_tokens, temperature=temperature
        )
        result["provider"] = self.provider.id
        return result

    # -- public capabilities ----------------------------------------------- #
    def chat(self, messages: list[dict], context: str = "") -> dict:
        system = CHAT_SYSTEM + (f"\n\nProject context:\n{context}" if context else "")
        return self._call(system, messages)

    def enhance_prompt(self, prompt: str, context: str = "") -> dict:
        system = ENHANCE_SYSTEM + (f"\n\nProject context:\n{context}" if context else "")
        return self._call(system, [{"role": "user", "content": prompt}])

    def plan(self, request: str, context: str = "") -> dict:
        system = PLAN_SYSTEM + (f"\n\nProject context:\n{context}" if context else "")
        result = self._call(system, [{"role": "user", "content": request}])
        plan = _extract_json(result["text"])
        if not isinstance(plan, dict) or "tasks" not in plan:
            raise AIError("model returned a plan in an unexpected shape")
        result["plan"] = plan
        return result

    def generate_files(self, request: str, context: str, plan: dict) -> dict:
        system = BUILD_SYSTEM
        user = (
            f"Request:\n{request}\n\nPlan:\n{json.dumps(plan)}\n\n"
            f"Project context:\n{context}\n\nReturn the JSON file changes."
        )
        result = self._call(system, [{"role": "user", "content": user}])
        payload = _extract_json(result["text"])
        if not isinstance(payload, dict) or "files" not in payload:
            raise AIError("model returned file changes in an unexpected shape")
        result["changes"] = payload
        return result
