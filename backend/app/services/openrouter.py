import json
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class OpenRouterError(Exception):
    """OpenRouter API error."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class OpenRouterClient:
    """Client for OpenRouter API with tool calling support."""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": f"https://{settings.APP_DOMAIN}",
                    "X-Title": settings.APP_DOMAIN,
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(300.0, connect=10.0),  # 5 min for long responses
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """
        Send a chat completion request to OpenRouter.

        Args:
            model: OpenRouter model ID (e.g., "anthropic/claude-sonnet-4-20250514")
            messages: List of message objects with role and content
            tools: Optional list of tool definitions for function calling
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response

        Returns:
            OpenRouter API response
        """
        client = await self._get_client()

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        logger.debug(f"OpenRouter request to {model}: {len(messages)} messages")

        try:
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            logger.debug(f"OpenRouter response: {data.get('usage', {})}")
            return data

        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            logger.error(f"OpenRouter HTTP error: {e.response.status_code} - {error_body}")
            raise OpenRouterError(f"API error: {error_body}", e.response.status_code) from e
        except httpx.RequestError as e:
            logger.error(f"OpenRouter request error: {e}")
            raise OpenRouterError(f"Request failed: {e}") from e

    async def chat_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        """
        Stream a chat completion response.

        Yields:
            Chunks of the response as they arrive
        """
        client = await self._get_client()

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        continue

    def extract_tool_calls(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract tool calls from an OpenRouter response."""
        choices = response.get("choices", [])
        if not choices:
            return []

        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls", [])

        return [
            {
                "id": tc.get("id"),
                "name": tc.get("function", {}).get("name"),
                "arguments": json.loads(tc.get("function", {}).get("arguments", "{}")),
            }
            for tc in tool_calls
        ]

    def extract_content(self, response: dict[str, Any]) -> str:
        """Extract text content from an OpenRouter response."""
        choices = response.get("choices", [])
        if not choices:
            return ""

        message = choices[0].get("message", {})
        return message.get("content", "") or ""

    def get_usage(self, response: dict[str, Any]) -> dict[str, int]:
        """Extract token usage from response."""
        return response.get(
            "usage",
            {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        )

    def has_tool_calls(self, response: dict[str, Any]) -> bool:
        """Check if response contains tool calls."""
        return len(self.extract_tool_calls(response)) > 0

    def is_finished(self, response: dict[str, Any]) -> bool:
        """Check if the response indicates completion (no more tool calls)."""
        choices = response.get("choices", [])
        if not choices:
            return True

        finish_reason = choices[0].get("finish_reason")
        return finish_reason == "stop" or (
            finish_reason != "tool_calls" and not self.has_tool_calls(response)
        )
