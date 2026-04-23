"""
LLM agent implementing LLMAgentPort via OpenRouter (OpenAI-compatible endpoint).
Handles JSON parse + repair retry and cost tracking.
"""

from __future__ import annotations

import json
import os
import re

import httpx

from src.domain.ports.llm_agent import LLMAgentPort, LLMMessage, LLMResponse


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"


class ClaudeAgent(LLMAgentPort):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")
        self._model = model or os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
        self._timeout = timeout_seconds

    async def call(
        self,
        system_prompt: str,
        messages: list[LLMMessage],
        max_tokens: int = 4096,
        temperature: float = 1.0,
        use_cache: bool = True,
        stream: bool = False,
    ) -> LLMResponse:
        if not self._api_key:
            raise ValueError("OPENROUTER_API_KEY not set")

        payload = self._build_payload(system_prompt, messages, max_tokens, temperature)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers=self._headers(),
                json=payload,
            )
            if response.status_code >= 400:
                raise ValueError(f"OpenRouter API {response.status_code}: {response.text}")
            data = response.json()

        return self._parse_response(data)

    async def call_json(
        self,
        system_prompt: str,
        messages: list[LLMMessage],
        max_tokens: int = 4096,
        temperature: float = 1.0,
        use_cache: bool = True,
    ) -> tuple[dict, LLMResponse]:
        """Call, parse as JSON, retry once on failure with a repair prompt."""
        resp = await self.call(system_prompt, messages, max_tokens, temperature, use_cache)
        parsed = _try_extract_json(resp.content)
        if parsed is not None:
            return parsed, resp

        # Retry with repair instruction
        repair_messages = list(messages) + [
            LLMMessage(role="assistant", content=resp.content),
            LLMMessage(
                role="user",
                content=(
                    "Your last response was not valid JSON. "
                    "Respond again with ONLY the valid JSON object, no prose, no markdown fences."
                ),
            ),
        ]
        resp2 = await self.call(system_prompt, repair_messages, max_tokens, temperature, use_cache)
        parsed2 = _try_extract_json(resp2.content)
        if parsed2 is None:
            raise ValueError(f"LLM did not return valid JSON after retry: {resp2.content[:500]}")
        return parsed2, resp2

    # ==== Helpers ====

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        system_prompt: str,
        messages: list[LLMMessage],
        max_tokens: int,
        temperature: float,
    ) -> dict:
        built_messages = []
        if system_prompt:
            built_messages.append({"role": "system", "content": system_prompt})
        for m in messages:
            built_messages.append({"role": m.role, "content": m.content})

        return {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": built_messages,
        }

    def _parse_response(self, data: dict) -> LLMResponse:
        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "") or ""
        usage = data.get("usage", {})
        return LLMResponse(
            content=content.strip(),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            cached_tokens=0,
            stop_reason=choice.get("finish_reason", ""),
            raw=data,
        )


def _try_extract_json(text: str) -> dict | None:
    """Parse JSON from a response; tolerate markdown fences and prose wrappers."""
    if not text:
        return None
    text = text.strip()

    # Strip markdown fences
    if text.startswith("```"):
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find the first {...} block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    return None