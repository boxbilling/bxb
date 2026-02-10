"""Tests for OpenRouter client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.openrouter import OpenRouterClient, OpenRouterError


class TestOpenRouterError:
    def test_error_with_message(self):
        error = OpenRouterError("Test error")
        assert str(error) == "Test error"
        assert error.status_code is None

    def test_error_with_status_code(self):
        error = OpenRouterError("API error", 429)
        assert str(error) == "API error"
        assert error.status_code == 429


class TestOpenRouterClient:
    @pytest.fixture
    def client(self):
        return OpenRouterClient(api_key="test-key")

    def test_init_with_api_key(self):
        client = OpenRouterClient(api_key="my-key")
        assert client.api_key == "my-key"
        assert client._client is None

    def test_init_without_api_key_uses_settings(self):
        with patch("app.services.openrouter.settings") as mock_settings:
            mock_settings.OPENROUTER_API_KEY = "settings-key"
            mock_settings.APP_DOMAIN = "test.com"
            client = OpenRouterClient()
            assert client.api_key == "settings-key"

    @pytest.mark.asyncio
    async def test_get_client_creates_new_client(self, client):
        with patch("app.services.openrouter.settings") as mock_settings:
            mock_settings.APP_DOMAIN = "test.com"

            http_client = await client._get_client()

            assert http_client is not None
            assert client._client is http_client

            # Cleanup
            await client.close()

    @pytest.mark.asyncio
    async def test_get_client_reuses_existing_client(self, client):
        with patch("app.services.openrouter.settings") as mock_settings:
            mock_settings.APP_DOMAIN = "test.com"

            http_client1 = await client._get_client()
            http_client2 = await client._get_client()

            assert http_client1 is http_client2

            # Cleanup
            await client.close()

    @pytest.mark.asyncio
    async def test_get_client_recreates_if_closed(self, client):
        with patch("app.services.openrouter.settings") as mock_settings:
            mock_settings.APP_DOMAIN = "test.com"

            http_client1 = await client._get_client()
            await client.close()

            http_client2 = await client._get_client()
            assert http_client1 is not http_client2

            # Cleanup
            await client.close()

    @pytest.mark.asyncio
    async def test_close_when_no_client(self, client):
        # Should not raise
        await client.close()

    @pytest.mark.asyncio
    async def test_close_when_already_closed(self, client):
        with patch("app.services.openrouter.settings") as mock_settings:
            mock_settings.APP_DOMAIN = "test.com"

            await client._get_client()
            await client.close()
            # Second close should not raise
            await client.close()

    @pytest.mark.asyncio
    async def test_chat_success(self, client):
        mock_response = {
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        mock_http_response = MagicMock()
        mock_http_response.json.return_value = mock_response
        mock_http_response.raise_for_status = MagicMock()

        mock_http_client = MagicMock()
        mock_http_client.post = AsyncMock(return_value=mock_http_response)
        mock_http_client.is_closed = False

        client._client = mock_http_client

        result = await client.chat(
            model="test-model",
            messages=[{"role": "user", "content": "Hi"}],
        )

        assert result == mock_response
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert call_args[0][0] == "/chat/completions"
        payload = call_args[1]["json"]
        assert payload["model"] == "test-model"
        assert payload["messages"] == [{"role": "user", "content": "Hi"}]

    @pytest.mark.asyncio
    async def test_chat_with_tools(self, client):
        mock_response = {"choices": [{"message": {"content": "Done"}}]}

        mock_http_response = MagicMock()
        mock_http_response.json.return_value = mock_response
        mock_http_response.raise_for_status = MagicMock()

        mock_http_client = MagicMock()
        mock_http_client.post = AsyncMock(return_value=mock_http_response)
        mock_http_client.is_closed = False

        client._client = mock_http_client

        tools = [{"type": "function", "function": {"name": "test_tool"}}]
        await client.chat(
            model="test-model",
            messages=[{"role": "user", "content": "Hi"}],
            tools=tools,
        )

        call_args = mock_http_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["tools"] == tools
        assert payload["tool_choice"] == "auto"

    @pytest.mark.asyncio
    async def test_chat_http_error(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limited"

        mock_http_client = MagicMock()
        mock_http_client.is_closed = False

        error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)
        mock_http_client.post = AsyncMock(side_effect=error)

        client._client = mock_http_client

        with pytest.raises(OpenRouterError) as exc_info:
            await client.chat(model="test", messages=[])

        assert exc_info.value.status_code == 429
        assert "Rate limited" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_chat_request_error(self, client):
        mock_http_client = MagicMock()
        mock_http_client.is_closed = False
        mock_http_client.post = AsyncMock(
            side_effect=httpx.RequestError("Connection failed", request=MagicMock())
        )

        client._client = mock_http_client

        with pytest.raises(OpenRouterError) as exc_info:
            await client.chat(model="test", messages=[])

        assert "Request failed" in str(exc_info.value)
        assert exc_info.value.status_code is None

    @pytest.mark.asyncio
    async def test_chat_stream(self, client):
        # Create mock async iterator for lines
        async def mock_aiter_lines():
            lines = [
                'data: {"choices": [{"delta": {"content": "Hello"}}]}',
                'data: {"choices": [{"delta": {"content": " World"}}]}',
                "data: [DONE]",
            ]
            for line in lines:
                yield line

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_lines = mock_aiter_lines

        # Create async context manager
        mock_stream_cm = MagicMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=None)

        mock_http_client = MagicMock()
        mock_http_client.is_closed = False
        mock_http_client.stream = MagicMock(return_value=mock_stream_cm)

        client._client = mock_http_client

        chunks = []
        async for chunk in client.chat_stream(model="test", messages=[]):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0]["choices"][0]["delta"]["content"] == "Hello"
        assert chunks[1]["choices"][0]["delta"]["content"] == " World"

    @pytest.mark.asyncio
    async def test_chat_stream_with_tools(self, client):
        async def mock_aiter_lines():
            lines = ['data: {"choices": [{"delta": {}}]}', "data: [DONE]"]
            for line in lines:
                yield line

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_lines = mock_aiter_lines

        mock_stream_cm = MagicMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=None)

        mock_http_client = MagicMock()
        mock_http_client.is_closed = False
        mock_http_client.stream = MagicMock(return_value=mock_stream_cm)

        client._client = mock_http_client

        tools = [{"type": "function", "function": {"name": "test"}}]
        chunks = []
        async for chunk in client.chat_stream(model="test", messages=[], tools=tools):
            chunks.append(chunk)

        # Verify tools were passed
        call_args = mock_http_client.stream.call_args
        payload = call_args[1]["json"]
        assert payload["tools"] == tools
        assert payload["tool_choice"] == "auto"
        assert payload["stream"] is True

    @pytest.mark.asyncio
    async def test_chat_stream_empty(self, client):
        """Test chat_stream with no data lines."""

        async def mock_aiter_lines():
            # No lines at all - empty stream
            return
            yield  # Make this a generator

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_lines = mock_aiter_lines

        mock_stream_cm = MagicMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=None)

        mock_http_client = MagicMock()
        mock_http_client.is_closed = False
        mock_http_client.stream = MagicMock(return_value=mock_stream_cm)

        client._client = mock_http_client

        chunks = []
        async for chunk in client.chat_stream(model="test", messages=[]):
            chunks.append(chunk)

        assert len(chunks) == 0

    @pytest.mark.asyncio
    async def test_chat_stream_non_data_lines(self, client):
        """Test that lines not starting with 'data: ' are skipped."""

        async def mock_aiter_lines():
            lines = [
                "",  # Empty line
                ": keep-alive",  # Comment line
                'data: {"choices": [{"delta": {"content": "OK"}}]}',
                "data: [DONE]",
            ]
            for line in lines:
                yield line

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_lines = mock_aiter_lines

        mock_stream_cm = MagicMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=None)

        mock_http_client = MagicMock()
        mock_http_client.is_closed = False
        mock_http_client.stream = MagicMock(return_value=mock_stream_cm)

        client._client = mock_http_client

        chunks = []
        async for chunk in client.chat_stream(model="test", messages=[]):
            chunks.append(chunk)

        # Should only return the valid data chunk
        assert len(chunks) == 1
        assert chunks[0]["choices"][0]["delta"]["content"] == "OK"

    @pytest.mark.asyncio
    async def test_chat_stream_invalid_json(self, client):
        async def mock_aiter_lines():
            lines = [
                "data: invalid-json",
                'data: {"choices": [{"delta": {"content": "OK"}}]}',
                "data: [DONE]",
            ]
            for line in lines:
                yield line

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_lines = mock_aiter_lines

        mock_stream_cm = MagicMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=None)

        mock_http_client = MagicMock()
        mock_http_client.is_closed = False
        mock_http_client.stream = MagicMock(return_value=mock_stream_cm)

        client._client = mock_http_client

        chunks = []
        async for chunk in client.chat_stream(model="test", messages=[]):
            chunks.append(chunk)

        # Should skip invalid JSON and return valid chunk
        assert len(chunks) == 1
        assert chunks[0]["choices"][0]["delta"]["content"] == "OK"

    def test_extract_tool_calls(self, client):
        response = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"location": "NYC"}',
                                },
                            }
                        ]
                    }
                }
            ]
        }

        tool_calls = client.extract_tool_calls(response)

        assert len(tool_calls) == 1
        assert tool_calls[0]["id"] == "call_123"
        assert tool_calls[0]["name"] == "get_weather"
        assert tool_calls[0]["arguments"] == {"location": "NYC"}

    def test_extract_tool_calls_empty_choices(self, client):
        response = {"choices": []}
        assert client.extract_tool_calls(response) == []

    def test_extract_tool_calls_no_choices(self, client):
        response = {}
        assert client.extract_tool_calls(response) == []

    def test_extract_tool_calls_no_tool_calls(self, client):
        response = {"choices": [{"message": {"content": "Hello"}}]}
        assert client.extract_tool_calls(response) == []

    def test_extract_content(self, client):
        response = {"choices": [{"message": {"content": "Hello world"}}]}
        assert client.extract_content(response) == "Hello world"

    def test_extract_content_empty_choices(self, client):
        response = {"choices": []}
        assert client.extract_content(response) == ""

    def test_extract_content_no_choices(self, client):
        response = {}
        assert client.extract_content(response) == ""

    def test_extract_content_none_content(self, client):
        response = {"choices": [{"message": {"content": None}}]}
        assert client.extract_content(response) == ""

    def test_get_usage(self, client):
        response = {"usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}
        usage = client.get_usage(response)
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50
        assert usage["total_tokens"] == 150

    def test_get_usage_missing(self, client):
        response = {}
        usage = client.get_usage(response)
        assert usage["prompt_tokens"] == 0
        assert usage["completion_tokens"] == 0
        assert usage["total_tokens"] == 0

    def test_has_tool_calls_true(self, client):
        response = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [{"id": "1", "function": {"name": "test", "arguments": "{}"}}]
                    }
                }
            ]
        }
        assert client.has_tool_calls(response) is True

    def test_has_tool_calls_false(self, client):
        response = {"choices": [{"message": {"content": "Hello"}}]}
        assert client.has_tool_calls(response) is False

    def test_is_finished_stop(self, client):
        response = {"choices": [{"finish_reason": "stop", "message": {"content": "Done"}}]}
        assert client.is_finished(response) is True

    def test_is_finished_tool_calls(self, client):
        response = {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "tool_calls": [{"id": "1", "function": {"name": "t", "arguments": "{}"}}]
                    },
                }
            ]
        }
        assert client.is_finished(response) is False

    def test_is_finished_no_choices(self, client):
        response = {"choices": []}
        assert client.is_finished(response) is True

    def test_is_finished_empty_response(self, client):
        response = {}
        assert client.is_finished(response) is True

    def test_is_finished_other_reason_no_tools(self, client):
        response = {"choices": [{"finish_reason": "length", "message": {"content": "..."}}]}
        assert client.is_finished(response) is True
