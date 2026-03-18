"""Async HTTP client for CLIProxyAPI (OpenAI-compatible)."""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, AsyncIterator

import httpx

from agent_teams.config import get_settings

# Ensure local connections bypass system proxy (e.g. Clash)
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
if "127.0.0.1" not in os.environ.get("NO_PROXY", ""):
    os.environ["NO_PROXY"] = os.environ.get("NO_PROXY", "") + ",127.0.0.1,localhost"


class LLMClient:
    """OpenAI-compatible async client that talks to CLIProxyAPI."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: int | None = None):
        settings = get_settings()
        self.base_url = (base_url or settings.proxy.base_url).rstrip("/")
        self.api_key = api_key or settings.proxy.api_key
        self.timeout = timeout or settings.proxy.timeout
        self._client: httpx.AsyncClient | None = None
        self._available_models: list[str] | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self.timeout, connect=10),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def list_models(self) -> list[str]:
        """Fetch available models from CLIProxyAPI."""
        if self._available_models is not None:
            return self._available_models
        client = await self._get_client()
        try:
            resp = await client.get("/v1/models")
            resp.raise_for_status()
            data = resp.json()
            self._available_models = [m["id"] for m in data.get("data", [])]
        except Exception:
            self._available_models = []
        return self._available_models

    async def pick_model(self, preferences: list[str]) -> str:
        """Pick the first available model from preference list."""
        available = await self.list_models()
        if not available:
            # If we can't query models, just use the first preference
            return preferences[0] if preferences else "claude-sonnet-4-20250514"
        for model in preferences:
            # Exact match or prefix match
            for avail in available:
                if model == avail or avail.startswith(model):
                    return avail
        # Fallback: return first preference anyway (let CLIProxyAPI handle routing)
        return preferences[0] if preferences else available[0]

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.5,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Non-streaming chat completion."""
        client = await self._get_client()
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)

        for attempt in range(4):
            resp = await client.post("/v1/chat/completions", json=payload)
            if resp.status_code == 429:
                wait = min(2 ** attempt * 5, 60)  # 5s, 10s, 20s, 60s
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()  # raise on final failure
        return {}

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.5,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Streaming chat completion, yields content deltas."""
        client = await self._get_client()
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)

        for attempt in range(4):
            try:
                async with client.stream("POST", "/v1/chat/completions", json=payload) as resp:
                    if resp.status_code == 429:
                        await resp.aread()
                        wait = min(2 ** attempt * 5, 60)
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            if content := delta.get("content"):
                                yield content
                        except (json.JSONDecodeError, IndexError, KeyError):
                            continue
                    return  # success, exit retry loop
            except httpx.HTTPStatusError:
                if attempt < 3:
                    await asyncio.sleep(min(2 ** attempt * 5, 60))
                else:
                    raise

    async def generate_image_via_gemini(
        self,
        prompt: str,
        model: str = "gemini-2.5-flash",
    ) -> dict[str, Any]:
        """Generate image using Nano Banana (Gemini image generation) via CLIProxyAPI.

        Uses the Gemini model's native image generation capability.
        The response may contain inline image data.
        """
        client = await self._get_client()
        messages = [
            {
                "role": "user",
                "content": prompt,
            }
        ]
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.8,
            "stream": False,
        }
        resp = await client.post("/v1/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()


# Singleton
_client: LLMClient | None = None


def get_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
