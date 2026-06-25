from datetime import UTC
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config.settings import get_settings

# =============================================================================
# Target 1: app/utils/api_clients.py
# =============================================================================


class TestLLMUnavailableError:
    def test_can_be_raised_and_caught(self) -> None:
        from app.utils.api_clients import LLMUnavailableError

        try:
            raise LLMUnavailableError("all providers down")
        except LLMUnavailableError as e:
            assert "all providers down" in str(e)

    def test_is_exception_subclass(self) -> None:
        from app.utils.api_clients import LLMUnavailableError

        assert issubclass(LLMUnavailableError, Exception)


class TestEmbeddingClient:
    @pytest.mark.asyncio
    async def test_get_openai_client_creates_client(self) -> None:
        from app.utils.api_clients import EmbeddingClient

        settings = get_settings()
        client = EmbeddingClient()
        assert client._openai_client is None

        with patch("app.utils.api_clients.AsyncOpenAI") as mock_openai:
            result = client._get_openai_client()

        mock_openai.assert_called_once_with(
            api_key=settings.openrouter_api_key,
            base_url="https://api.openai.com/v1",
        )
        assert result is not None
        assert client._openai_client is not None

    @pytest.mark.asyncio
    async def test_get_openai_client_returns_cached(self) -> None:
        from app.utils.api_clients import EmbeddingClient

        client = EmbeddingClient()
        fake = MagicMock()
        client._openai_client = fake
        with patch("app.utils.api_clients.AsyncOpenAI") as mock_openai:
            result = client._get_openai_client()
        mock_openai.assert_not_called()
        assert result is fake

    @pytest.mark.asyncio
    async def test_embed_success(self) -> None:
        from app.utils.api_clients import EmbeddingClient

        settings = get_settings()
        client = EmbeddingClient()
        fake_embedding = [0.1, 0.2, 0.3]

        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(
            return_value=MagicMock(data=[MagicMock(embedding=fake_embedding)])
        )
        client._openai_client = mock_client

        result = await client.embed("hello world")

        mock_client.embeddings.create.assert_awaited_once_with(
            model=settings.openai_embedding_model,
            input="hello world",
            dimensions=settings.openai_embedding_dimensions,
        )
        assert result == fake_embedding

    @pytest.mark.asyncio
    async def test_embed_fallback_to_ollama_success(self) -> None:
        from app.utils.api_clients import EmbeddingClient

        client = EmbeddingClient()
        fake_embedding = [0.4, 0.5, 0.6]

        openai_mock = AsyncMock()
        openai_mock.embeddings.create = AsyncMock(side_effect=Exception("API error"))
        client._openai_client = openai_mock

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"embedding": fake_embedding})

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client

        with patch("app.utils.api_clients.httpx.AsyncClient", return_value=mock_client):
            result = await client.embed("hello world")

        assert result == fake_embedding

    @pytest.mark.asyncio
    async def test_embed_all_providers_fail_returns_zero_vector(self) -> None:
        from app.utils.api_clients import EmbeddingClient

        client = EmbeddingClient()

        openai_mock = AsyncMock()
        openai_mock.embeddings.create = AsyncMock(side_effect=Exception("API error"))
        client._openai_client = openai_mock

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Ollama offline"))
        mock_client.__aenter__.return_value = mock_client

        with patch("app.utils.api_clients.httpx.AsyncClient", return_value=mock_client):
            result = await client.embed("hello world")

        assert result == [0.0] * 768

    @pytest.mark.asyncio
    async def test_fallback_ollama_embed_success(self) -> None:
        from app.utils.api_clients import EmbeddingClient

        client = EmbeddingClient()
        fake_embedding = [0.7, 0.8, 0.9]

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"embedding": fake_embedding})

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client

        with patch("app.utils.api_clients.httpx.AsyncClient", return_value=mock_client):
            result = await client._fallback_ollama_embed("test text")

        assert result == fake_embedding

    @pytest.mark.asyncio
    async def test_fallback_ollama_embed_failure_returns_zero_vector(self) -> None:
        from app.utils.api_clients import EmbeddingClient

        client = EmbeddingClient()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
        mock_client.__aenter__.return_value = mock_client

        with patch("app.utils.api_clients.httpx.AsyncClient", return_value=mock_client):
            result = await client._fallback_ollama_embed("test text")

        assert result == [0.0] * 768


class TestLLMClient:
    @staticmethod
    def _make_httpx_post_mock(mock_response: MagicMock) -> tuple[AsyncMock, MagicMock]:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client
        return mock_client, mock_response

    @pytest.mark.asyncio
    async def test_fallback_ollama_success(self) -> None:
        from app.utils.api_clients import LLMClient

        settings = get_settings()
        client = LLMClient()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"message": {"content": "Ollama reply"}})

        mock_client, _ = self._make_httpx_post_mock(mock_response)
        with patch("app.utils.api_clients.httpx.AsyncClient", return_value=mock_client):
            result = await client._fallback_ollama(
                "qwen2.5",
                [{"role": "user", "content": "hello"}],
                temperature=0.5,
            )

        assert result.content == "Ollama reply"
        assert result.provider == "ollama"
        assert result.degraded is True
        assert result.model == settings.ollama_fallback_model

    @pytest.mark.asyncio
    async def test_fallback_ollama_failure_raises_llm_unavailable(self) -> None:
        from app.utils.api_clients import LLMClient, LLMUnavailableError

        client = LLMClient()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Ollama unreachable"))
        mock_client.__aenter__.return_value = mock_client

        with patch("app.utils.api_clients.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(LLMUnavailableError) as exc:
                await client._fallback_ollama(
                    "qwen2.5",
                    [{"role": "user", "content": "hello"}],
                )
            assert "OpenRouter and Ollama unavailable" in str(exc.value)

    @pytest.mark.asyncio
    async def test_complete_method(self) -> None:
        from app.utils.api_clients import LLMClient, LLMResponse

        get_settings()
        client = LLMClient()
        fake_response = LLMResponse(
            content="test completion", model="openai/gpt-4o-2024-11-20", provider="openrouter"
        )

        with patch.object(client, "chat", AsyncMock(return_value=fake_response)) as mock_chat:
            result = await client.complete(
                model=MagicMock(),
                system="You are a helpful assistant",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.3,
                max_tokens=2048,
            )

        mock_chat.assert_awaited_once()
        call_args, call_kwargs = mock_chat.call_args
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["max_tokens"] == 2048
        messages = call_args[1]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant"
        assert messages[1]["role"] == "user"
        assert result.content == "test completion"

    def test_get_openai_client_llm_creates_and_caches(self) -> None:
        from app.utils.api_clients import LLMClient

        settings = get_settings()
        client = LLMClient()
        assert client._openai_client is None

        with patch("app.utils.api_clients.AsyncOpenAI") as mock_openai:
            result1 = client._get_openai_client()

        mock_openai.assert_called_once_with(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
        assert result1 is not None
        assert client._openai_client is result1

        with patch("app.utils.api_clients.AsyncOpenAI") as mock_openai:
            result2 = client._get_openai_client()
        mock_openai.assert_not_called()
        assert result2 is result1

    def test_cache_key_deterministic(self) -> None:
        from app.utils.api_clients import LLMClient

        client = LLMClient()
        key1 = client._cache_key("gpt-4", [{"role": "user", "content": "hi"}], 0.7)
        key2 = client._cache_key("gpt-4", [{"role": "user", "content": "hi"}], 0.7)
        assert key1 == key2
        assert isinstance(key1, str)
        assert len(key1) == 64

        key3 = client._cache_key("gpt-4", [{"role": "user", "content": "bye"}], 0.7)
        assert key1 != key3

    @pytest.mark.asyncio
    async def test_chat_success(self) -> None:
        from app.utils.api_clients import LLMClient

        get_settings()
        client = LLMClient()

        fake_choice = MagicMock()
        fake_choice.message.content = "Hello from LLM"
        fake_response = MagicMock()
        fake_response.choices = [fake_choice]

        mock_openai = AsyncMock()
        mock_openai.chat.completions.create = AsyncMock(return_value=fake_response)
        client._openai_client = mock_openai

        result = await client.chat("openai/gpt-4o", [{"role": "user", "content": "hi"}])

        assert result.content == "Hello from LLM"
        assert result.model == "openai/gpt-4o"
        assert result.provider == "openrouter"
        assert result.degraded is False

    @pytest.mark.asyncio
    async def test_chat_caches_response(self) -> None:
        from app.utils.api_clients import LLMClient

        client = LLMClient()
        client._llm_cache.clear()

        fake_choice = MagicMock()
        fake_choice.message.content = "Cached response"
        fake_response = MagicMock()
        fake_response.choices = [fake_choice]

        mock_openai = AsyncMock()
        mock_openai.chat.completions.create = AsyncMock(return_value=fake_response)
        client._openai_client = mock_openai

        result1 = await client.chat("gpt-4", [{"role": "user", "content": "test"}])
        assert result1.content == "Cached response"

        mock_openai.chat.completions.create = AsyncMock(side_effect=Exception("should not call"))
        result2 = await client.chat("gpt-4", [{"role": "user", "content": "test"}])
        assert result2.content == "Cached response"
        assert result2 is result1

    @pytest.mark.asyncio
    async def test_chat_with_tools_does_not_cache(self) -> None:
        from app.utils.api_clients import LLMClient

        client = LLMClient()
        client._llm_cache.clear()

        fake_choice = MagicMock()
        fake_choice.message.content = "With tools"
        fake_response = MagicMock()
        fake_response.choices = [fake_choice]

        mock_openai = AsyncMock()
        mock_openai.chat.completions.create = AsyncMock(return_value=fake_response)
        client._openai_client = mock_openai

        result1 = await client.chat(
            "gpt-4",
            [{"role": "user", "content": "test"}],
            tools=[{"type": "function", "function": {"name": "test"}}],
        )
        assert result1.content == "With tools"

        result2 = await client.chat(
            "gpt-4",
            [{"role": "user", "content": "test"}],
            tools=[{"type": "function", "function": {"name": "test"}}],
        )
        assert result2 is not result1

    @pytest.mark.asyncio
    async def test_chat_fallback_on_error(self) -> None:
        from app.utils.api_clients import LLMClient

        client = LLMClient()

        mock_openai = AsyncMock()
        mock_openai.chat.completions.create = AsyncMock(side_effect=Exception("OpenRouter down"))
        client._openai_client = mock_openai

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"message": {"content": "Ollama fallback"}})

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client

        with patch("app.utils.api_clients.httpx.AsyncClient", return_value=mock_client):
            result = await client.chat(
                "gpt-4", [{"role": "user", "content": "hi"}], temperature=0.5
            )  # noqa: E501

        assert result.content == "Ollama fallback"
        assert result.provider == "ollama"
        assert result.degraded is True

    @pytest.mark.asyncio
    async def test_chat_cache_disabled_does_not_cache(self) -> None:
        from app.utils.api_clients import LLMClient

        settings = get_settings()
        settings.llm_cache_enabled = False
        client = LLMClient()
        client._llm_cache.clear()

        fake_choice = MagicMock()
        fake_choice.message.content = "No cache"
        fake_response = MagicMock()
        fake_response.choices = [fake_choice]

        mock_openai = AsyncMock()
        mock_openai.chat.completions.create = AsyncMock(return_value=fake_response)
        client._openai_client = mock_openai

        result1 = await client.chat("gpt-4", [{"role": "user", "content": "test"}])
        result2 = await client.chat("gpt-4", [{"role": "user", "content": "test"}])
        assert result1 is not result2

    def test_select_model_routing(self) -> None:
        from app.utils.api_clients import LLMClient

        settings = get_settings()
        client = LLMClient()

        assert client._select_model("code") == settings.model_for_code
        assert client._select_model("content") == settings.model_for_content
        assert client._select_model("analysis") == settings.model_for_analysis
        assert client._select_model("commerce") == settings.model_for_commerce
        assert client._select_model("write") == settings.model_for_content
        assert client._select_model("image") == settings.model_for_content
        assert client._select_model("analyze") == settings.model_for_analysis
        assert client._select_model("segment") == settings.model_for_analysis
        assert client._select_model("catalog") == settings.model_for_commerce
        assert client._select_model("pricing") == settings.model_for_analysis
        assert client._select_model("faq") == settings.model_for_content
        assert client._select_model("unknown") == settings.model_for_default

    @pytest.mark.asyncio
    async def test_chat_with_model_selection(self) -> None:
        from app.utils.api_clients import LLMClient

        settings = get_settings()
        client = LLMClient()

        fake_choice = MagicMock()
        fake_choice.message.content = "Model selected"
        fake_response = MagicMock()
        fake_response.choices = [fake_choice]

        mock_openai = AsyncMock()
        mock_openai.chat.completions.create = AsyncMock(return_value=fake_response)
        client._openai_client = mock_openai

        result = await client.chat_with_model_selection(
            "code", [{"role": "user", "content": "write code"}]
        )
        assert result.content == "Model selected"
        assert result.model == settings.model_for_code

    def test_clear_cache(self) -> None:
        from app.utils.api_clients import LLMClient

        client = LLMClient()
        client._llm_cache["dummy"] = MagicMock()
        client.clear_cache()
        assert len(client._llm_cache) == 0


# =============================================================================
# Target 2: app/utils/notifications.py
# =============================================================================


class TestNotificationManager:
    @staticmethod
    def _make_httpx_client_mock(mock_response: MagicMock) -> AsyncMock:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client
        return mock_client

    @pytest.mark.asyncio
    async def test_send_console(self) -> None:
        from app.utils.notifications import NotificationManager

        nm = NotificationManager()
        result = await nm.send("console", "Test Title", "Test message")
        assert result is True

    @pytest.mark.asyncio
    async def test_send_unknown_channel(self) -> None:
        from app.utils.notifications import NotificationManager

        nm = NotificationManager()
        result = await nm.send("sms", "Title", "Msg")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_handler_exception_returns_false(self) -> None:
        from app.utils.notifications import NotificationManager

        nm = NotificationManager()
        nm._send_console = AsyncMock(side_effect=Exception("crash"))  # type: ignore[method-assign]
        result = await nm.send("console", "Title", "Msg")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_slack_with_details(self) -> None:
        from app.utils.notifications import NotificationManager

        settings = get_settings()
        settings.slack_webhook_url = "https://hooks.slack.com/test"
        nm = NotificationManager()
        nm.settings = settings

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = self._make_httpx_client_mock(mock_response)

        with patch("app.utils.notifications.httpx.AsyncClient", return_value=mock_client):
            result = await nm.send(
                "slack", "Alert", "Something happened", details={"severity": "high"}
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_slack_no_webhook_returns_early(self) -> None:
        from app.utils.notifications import NotificationManager

        settings = get_settings()
        settings.slack_webhook_url = ""
        nm = NotificationManager()
        nm.settings = settings

        with patch("app.utils.notifications.httpx.AsyncClient") as mock_httpx:
            result = await nm.send("slack", "Title", "Msg")
        mock_httpx.assert_not_called()
        assert result is True

    @pytest.mark.asyncio
    async def test_send_discord_with_webhook(self) -> None:
        from app.utils.notifications import NotificationManager

        settings = get_settings()
        settings.discord_webhook_url = "https://discord.com/webhook/test"
        nm = NotificationManager()
        nm.settings = settings

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = self._make_httpx_client_mock(mock_response)

        with patch("app.utils.notifications.httpx.AsyncClient", return_value=mock_client):
            result = await nm.send(
                "discord", "Alert", "Something happened", details={"env": "prod"}
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_discord_no_webhook_returns_early(self) -> None:
        from app.utils.notifications import NotificationManager

        settings = get_settings()
        settings.discord_webhook_url = ""
        nm = NotificationManager()
        nm.settings = settings

        with patch("app.utils.notifications.httpx.AsyncClient") as mock_httpx:
            result = await nm.send("discord", "Title", "Msg")
        mock_httpx.assert_not_called()
        assert result is True

    @pytest.mark.asyncio
    async def test_notify_all_without_slack(self) -> None:
        from app.utils.notifications import NotificationManager

        nm = NotificationManager()
        result = await nm.notify_all("Global", "announcement")  # type: ignore[func-returns-value]
        assert result is None

    @pytest.mark.asyncio
    async def test_notify_all_with_slack(self) -> None:
        from app.utils.notifications import NotificationManager

        settings = get_settings()
        settings.slack_webhook_url = "https://hooks.slack.com/test"
        nm = NotificationManager()
        nm.settings = settings

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = self._make_httpx_client_mock(mock_response)

        with patch("app.utils.notifications.httpx.AsyncClient", return_value=mock_client):
            result = await nm.notify_all("Global", "announcement", details={"version": "5.0"})  # type: ignore[func-returns-value]
        assert result is None

    def test_get_notifications_singleton(self) -> None:
        from app.utils.notifications import get_notifications

        nm1 = get_notifications()
        nm2 = get_notifications()
        assert nm1 is nm2


# =============================================================================
# Target 3: app/agents/sub_agent.py
# =============================================================================


class TestSubAgent:
    def test_get_sub_agent_builtin(self) -> None:
        from app.agents.sub_agent import get_sub_agent

        agent = get_sub_agent("debugger")
        assert agent is not None
        assert agent.config.name == "Debugger"

    def test_get_sub_agent_builtin_with_tools(self) -> None:
        from app.agents.sub_agent import get_sub_agent

        tools = MagicMock()
        agent = get_sub_agent("planner", tools=tools)
        assert agent is not None
        assert agent.tools is tools

    def test_get_sub_agent_custom_config(self) -> None:
        from app.agents.sub_agent import get_sub_agent

        fake_yaml = """---
name: CustomAgent
model: openai/gpt-4
temperature: 0.5
tools:
  - read
  - bash
---
This is the system prompt for the custom agent.
"""
        with (
            patch(
                "app.agents.sub_agent.os.path.expanduser",
                return_value="/fake/.agentos/subagents/custom.md",
            ),  # noqa: E501
            patch("app.agents.sub_agent.os.path.exists", return_value=True),
            patch(
                "builtins.open",
                MagicMock(
                    return_value=MagicMock(
                        __enter__=MagicMock(
                            return_value=MagicMock(read=MagicMock(return_value=fake_yaml))
                        )
                    )
                ),
            ),
        ):
            agent = get_sub_agent("custom")
        assert agent is not None
        assert agent.config.name == "CustomAgent"
        assert agent.config.model == "openai/gpt-4"
        assert agent.config.temperature == 0.5
        assert agent.config.tools == ["read", "bash"]

    def test_get_sub_agent_not_found(self) -> None:
        from app.agents.sub_agent import get_sub_agent

        with (
            patch(
                "app.agents.sub_agent.os.path.expanduser",
                return_value="/fake/.agentos/subagents/nope.md",
            ),  # noqa: E501
            patch("app.agents.sub_agent.os.path.exists", return_value=False),
        ):
            agent = get_sub_agent("nope")
        assert agent is None

    def test_load_custom_config_success(self) -> None:
        from app.agents.sub_agent import _load_custom_config

        fake_yaml = """---
name: TestAgent
model: anthropic/claude-3
temperature: 0.1
tools:
  - read
  - search
---
You are a test agent.
"""
        fake_file = MagicMock()
        fake_file.__enter__.return_value.read.return_value = fake_yaml
        with patch("builtins.open", return_value=fake_file):
            config = _load_custom_config("/fake/path/test.md")
        assert config is not None
        assert config.name == "TestAgent"
        assert config.model == "anthropic/claude-3"
        assert config.temperature == 0.1
        assert config.tools == ["read", "search"]
        assert config.system_prompt == "You are a test agent."

    def test_load_custom_config_no_frontmatter(self) -> None:
        from app.agents.sub_agent import _load_custom_config

        fake_file = MagicMock()
        fake_file.__enter__.return_value.read.return_value = (
            "Just a plain markdown file without frontmatter."  # noqa: E501
        )
        with patch("builtins.open", return_value=fake_file):
            config = _load_custom_config("/fake/path/no_meta.md")
        assert config is None

    def test_load_custom_config_missing_file(self) -> None:
        from app.agents.sub_agent import _load_custom_config

        with patch("builtins.open", side_effect=FileNotFoundError("no such file")):
            config = _load_custom_config("/fake/missing.md")
        assert config is None

    def test_load_custom_config_invalid_yaml(self) -> None:
        from app.agents.sub_agent import _load_custom_config

        fake_content = """---
name: TestAgent
invalid_yaml: [unclosed
---
System prompt here.
"""
        fake_file = MagicMock()
        fake_file.__enter__.return_value.read.return_value = fake_content
        with patch("builtins.open", return_value=fake_file):
            config = _load_custom_config("/fake/path/bad.yaml")
        assert config is None

    def test_get_or_create_sub_agent_new(self) -> None:
        from app.agents.sub_agent import get_or_create_sub_agent, sub_agent_registry

        sub_agent_registry.clear()
        agent = get_or_create_sub_agent("debugger")
        assert agent is not None
        assert "debugger" in sub_agent_registry
        assert sub_agent_registry["debugger"] is agent

    def test_get_or_create_sub_agent_cached(self) -> None:
        from app.agents.sub_agent import get_or_create_sub_agent, sub_agent_registry

        sub_agent_registry.clear()
        agent1 = get_or_create_sub_agent("debugger")
        agent2 = get_or_create_sub_agent("debugger")
        assert agent1 is agent2

    def test_get_or_create_sub_agent_not_found(self) -> None:
        from app.agents.sub_agent import get_or_create_sub_agent, sub_agent_registry

        sub_agent_registry.clear()
        with (
            patch(
                "app.agents.sub_agent.os.path.expanduser",
                return_value="/fake/.agentos/subagents/unknown.md",
            ),  # noqa: E501
            patch("app.agents.sub_agent.os.path.exists", return_value=False),
        ):
            agent = get_or_create_sub_agent("unknown")
        assert agent is None

    def test_route_to_sub_agent_verifier(self) -> None:
        from app.agents.sub_agent import route_to_sub_agent

        assert route_to_sub_agent("please verify this code") == "verifier"
        assert route_to_sub_agent("validate the output") == "verifier"
        assert route_to_sub_agent("run tests") == "verifier"
        assert route_to_sub_agent("check quality") == "verifier"
        assert route_to_sub_agent("lint check") == "verifier"

    def test_route_to_sub_agent_explorer(self) -> None:
        from app.agents.sub_agent import route_to_sub_agent

        assert route_to_sub_agent("explore this codebase") == "explorer"
        assert route_to_sub_agent("find where is the config") == "explorer"
        assert route_to_sub_agent("search for the error handler") == "explorer"
        assert route_to_sub_agent("what is the architecture") == "explorer"

    def test_route_to_sub_agent_code_reviewer(self) -> None:
        from app.agents.sub_agent import route_to_sub_agent

        assert route_to_sub_agent("review this PR") == "code_reviewer"
        assert route_to_sub_agent("audit the security") == "code_reviewer"
        assert route_to_sub_agent("security check") == "code_reviewer"

    def test_route_to_sub_agent_planner(self) -> None:
        from app.agents.sub_agent import route_to_sub_agent

        assert route_to_sub_agent("plan the implementation") == "planner"
        assert route_to_sub_agent("design the approach") == "planner"
        assert route_to_sub_agent("how to approach this") == "planner"
        assert route_to_sub_agent("unknown task") == "planner"

    def test_route_to_sub_agent_debugger(self) -> None:
        from app.agents.sub_agent import route_to_sub_agent

        assert route_to_sub_agent("fix this error") == "debugger"
        assert route_to_sub_agent("debug the exception") == "debugger"
        assert route_to_sub_agent("handle crash") == "debugger"
        assert route_to_sub_agent("traceback shows issue") == "debugger"

    @pytest.mark.asyncio
    async def test_sub_agent_run_success(self) -> None:
        from app.agents.sub_agent import SubAgent, SubAgentConfig

        config = SubAgentConfig(name="TestAgent", system_prompt="You are a test agent.")
        agent = SubAgent(config)

        fake_response = MagicMock()
        fake_response.content = '{"result": "success", "score": 42}'
        agent.llm.chat = AsyncMock(return_value=fake_response)  # type: ignore[method-assign]  # type: ignore[method-assign]

        result = await agent.run("test task")
        assert result == {"result": "success", "score": 42}

    @pytest.mark.asyncio
    async def test_sub_agent_run_with_context(self) -> None:
        from app.agents.sub_agent import SubAgent, SubAgentConfig

        config = SubAgentConfig(name="TestAgent", system_prompt="You are a test agent.")
        agent = SubAgent(config)

        fake_response = MagicMock()
        fake_response.content = '{"ok": true}'
        agent.llm.chat = AsyncMock(return_value=fake_response)  # type: ignore[method-assign]

        result = await agent.run("test task", context={"file": "main.py", "line": 42})
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_sub_agent_run_strips_markdown_code_block(self) -> None:
        from app.agents.sub_agent import SubAgent, SubAgentConfig

        config = SubAgentConfig(name="TestAgent", system_prompt="You are a test agent.")
        agent = SubAgent(config)

        fake_response = MagicMock()
        fake_response.content = '```json\n{"key": "value"}\n```'
        agent.llm.chat = AsyncMock(return_value=fake_response)  # type: ignore[method-assign]

        result = await agent.run("test task")
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_sub_agent_run_invalid_json_returns_raw(self) -> None:
        from app.agents.sub_agent import SubAgent, SubAgentConfig

        config = SubAgentConfig(name="TestAgent", system_prompt="You are a test agent.")
        agent = SubAgent(config)

        fake_response = MagicMock()
        fake_response.content = "This is not valid JSON at all"
        agent.llm.chat = AsyncMock(return_value=fake_response)  # type: ignore[method-assign]

        result = await agent.run("test task")
        assert result == {"raw_response": "This is not valid JSON at all", "parsed": False}


# =============================================================================
# Target 4: app/mcp/server.py
# =============================================================================


class TestMCPServer:
    @pytest.mark.asyncio
    async def test_call_tool_success(self) -> None:
        from app.mcp.server import MCPServer

        server = MCPServer("test-server", "http://localhost:9000")
        mock_data = {"result": "ok"}

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=mock_data)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client

        with patch("app.mcp.server.httpx.AsyncClient", return_value=mock_client):
            result = await server.call_tool("deploy", {"env": "staging"})

        assert result == mock_data

    @pytest.mark.asyncio
    async def test_call_tool_with_api_key(self) -> None:
        from app.mcp.server import MCPServer

        server = MCPServer("test-server", "http://localhost:9000", api_key="sk-123")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={})

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client

        with patch("app.mcp.server.httpx.AsyncClient", return_value=mock_client):
            await server.call_tool("deploy")

        _, call_kwargs = mock_client.post.call_args
        assert call_kwargs["headers"]["Authorization"] == "Bearer sk-123"

    @pytest.mark.asyncio
    async def test_call_tool_failure_returns_error_dict(self) -> None:
        from app.mcp.server import MCPServer

        server = MCPServer("test-server", "http://localhost:9000")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
        mock_client.__aenter__.return_value = mock_client

        with patch("app.mcp.server.httpx.AsyncClient", return_value=mock_client):
            result = await server.call_tool("deploy")

        assert "error" in result
        assert "connection refused" in result["error"]

    @pytest.mark.asyncio
    async def test_list_tools_success(self) -> None:
        from app.mcp.server import MCPServer

        server = MCPServer("test-server", "http://localhost:9000")
        mock_tools = [{"name": "deploy", "description": "Deploy service"}]

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"tools": mock_tools})

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client

        with patch("app.mcp.server.httpx.AsyncClient", return_value=mock_client):
            result = await server.list_tools()

        assert result == mock_tools

    @pytest.mark.asyncio
    async def test_list_tools_failure_returns_empty_list(self) -> None:
        from app.mcp.server import MCPServer

        server = MCPServer("test-server", "http://localhost:9000")

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("timeout"))
        mock_client.__aenter__.return_value = mock_client

        with patch("app.mcp.server.httpx.AsyncClient", return_value=mock_client):
            result = await server.list_tools()

        assert result == []

    def test_endpoint_strips_trailing_slash(self) -> None:
        from app.mcp.server import MCPServer

        server = MCPServer("test", "http://localhost:9000/")
        assert server.endpoint == "http://localhost:9000"


class TestMCPRegistry:
    def test_register_and_get(self) -> None:
        from app.mcp.server import MCPRegistry

        registry = MCPRegistry()
        registry.register("my-server", "http://localhost:9000")
        server = registry.get("my-server")
        assert server is not None
        assert server.name == "my-server"
        assert server.endpoint == "http://localhost:9000"

    def test_get_missing_returns_none(self) -> None:
        from app.mcp.server import MCPRegistry

        registry = MCPRegistry()
        assert registry.get("nonexistent") is None

    def test_register_with_api_key(self) -> None:
        from app.mcp.server import MCPRegistry

        registry = MCPRegistry()
        registry.register("secure", "http://localhost:9001", api_key="sk-secret")
        server = registry.get("secure")
        assert server is not None
        assert server.api_key == "sk-secret"

    def test_unregister_existing(self) -> None:
        from app.mcp.server import MCPRegistry

        registry = MCPRegistry()
        registry.register("tmp", "http://localhost:9000")
        registry.unregister("tmp")
        assert registry.get("tmp") is None

    def test_unregister_missing_does_not_raise(self) -> None:
        from app.mcp.server import MCPRegistry

        registry = MCPRegistry()
        registry.unregister("nonexistent")

    @pytest.mark.asyncio
    async def test_call_tool_server_found(self) -> None:
        from app.mcp.server import MCPRegistry

        registry = MCPRegistry()
        registry.register("my-server", "http://localhost:9000")

        with patch.object(
            registry.get("my-server"), "call_tool", AsyncMock(return_value={"result": "ok"})
        ) as mock_call:
            result = await registry.call_tool("my-server", "deploy", {"env": "prod"})

        assert result == {"result": "ok"}
        mock_call.assert_awaited_once_with("deploy", {"env": "prod"})

    @pytest.mark.asyncio
    async def test_call_tool_server_not_found(self) -> None:
        from app.mcp.server import MCPRegistry

        registry = MCPRegistry()
        result = await registry.call_tool("ghost", "deploy")
        assert result == {"error": "MCP server 'ghost' not found"}

    def test_list_servers_empty(self) -> None:
        from app.mcp.server import MCPRegistry

        registry = MCPRegistry()
        assert registry.list_servers() == []

    def test_list_servers_populated(self) -> None:
        from app.mcp.server import MCPRegistry

        registry = MCPRegistry()
        registry.register("s1", "http://localhost:9000")
        registry.register("s2", "http://localhost:9001")
        servers = registry.list_servers()
        assert len(servers) == 2
        names = [s["name"] for s in servers]
        assert "s1" in names
        assert "s2" in names

    def test_get_mcp_registry_singleton(self) -> None:
        from app.mcp.server import get_mcp_registry

        r1 = get_mcp_registry()
        r2 = get_mcp_registry()
        assert r1 is r2


# =============================================================================
# Audit v7.2.2 — Coverage gaps (69 lines)
# =============================================================================


class TestBaseAgentMultimodal:
    """Cover app/agents/base.py:182-205 — _build_multimodal_messages"""

    def _make_agent(self) -> Any:
        from app.agents.base import BaseAgent

        class _TestAgent(BaseAgent):
            name = "test"

            async def _run(
                self,
                action: str,
                params: dict,
                session_id: str,
                trace_id: str,
                attachments: list | None = None,
            ) -> Any:
                return {"ok": True}

        return _TestAgent()

    def test_no_images_returns_unchanged(self) -> None:
        agent = self._make_agent()
        msgs = [{"role": "user", "content": "hello"}]
        result = agent._build_multimodal_messages(msgs)
        assert result == msgs

    def test_with_images_converts_to_multimodal(self) -> None:
        agent = self._make_agent()
        agent._attachments = [
            {"mime_type": "image/png", "data_base64": "abc123"},
        ]
        msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "describe this"}]
        result = agent._build_multimodal_messages(msgs)
        assert isinstance(result[1]["content"], list)
        assert result[1]["content"][0]["type"] == "text"
        assert result[1]["content"][1]["type"] == "image_url"


class TestIntelligenceAPIGetSession:
    """Cover app/api/intelligence.py:28-30 — _get_session engine creation"""

    @pytest.mark.asyncio
    async def test_get_session_creates_engine(self) -> None:
        from app.api import intelligence

        intelligence._engine = None
        intelligence._session_factory = None
        with patch("app.api.intelligence.create_async_engine") as mock_ce:
            with patch("app.api.intelligence.async_sessionmaker") as mock_sm:
                mock_sm.return_value = MagicMock(return_value=MagicMock())
                result = await intelligence._get_session()
                mock_ce.assert_called_once()
                assert result is not None


class TestAgentBusExceptions:
    """Cover app/bus/agent_bus.py:67-69, 93-94, 107-108, 113-115, 121-122, 146-147, 153-154"""

    @pytest.mark.asyncio
    async def test_connect_exception(self) -> None:
        from app.bus.agent_bus import AgentBus

        with patch("app.bus.agent_bus.Redis.from_url", side_effect=Exception("conn fail")):
            bus = AgentBus(redis_url="redis://bad:6379")
            assert bus._redis is None

    @pytest.mark.asyncio
    async def test_publish_no_redis(self) -> None:
        from app.bus.agent_bus import AgentBus, BusMessage

        bus = AgentBus(redis_url="redis://bad:6379")
        bus._redis = None
        msg = BusMessage(sender="s", recipient="r", topic="t", payload={})
        await bus.publish(msg)

    @pytest.mark.asyncio
    async def test_publish_exception(self) -> None:
        from app.bus.agent_bus import AgentBus, BusMessage

        bus = AgentBus(redis_url="redis://bad:6379")
        bus._redis = MagicMock()
        bus._redis.publish = AsyncMock(side_effect=Exception("pub fail"))
        msg = BusMessage(sender="s", recipient="r", topic="t", payload={})
        await bus.publish(msg)

    @pytest.mark.asyncio
    async def test_subscribe_no_redis(self) -> None:
        from app.bus.agent_bus import AgentBus

        bus = AgentBus(redis_url="redis://bad:6379")
        bus._redis = None
        queue = await bus.subscribe("test")
        assert queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_subscribe_exception(self) -> None:
        from app.bus.agent_bus import AgentBus

        bus = AgentBus(redis_url="redis://bad:6379")
        bus._redis = MagicMock()
        pubsub = MagicMock()
        pubsub.subscribe = AsyncMock(side_effect=Exception("sub fail"))
        bus._redis.pubsub.return_value = pubsub
        queue = await bus.subscribe("test")
        assert queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_close_pubsub_exception(self) -> None:
        from app.bus.agent_bus import AgentBus

        bus = AgentBus(redis_url="redis://bad:6379")
        bus._pubsub = MagicMock()
        bus._pubsub.unsubscribe = AsyncMock(side_effect=Exception("unsub fail"))
        bus._pubsub.close = AsyncMock(side_effect=Exception("close fail"))
        bus._redis = MagicMock()
        bus._redis.aclose = AsyncMock()
        await bus.close()

    @pytest.mark.asyncio
    async def test_close_redis_exception(self) -> None:
        from app.bus.agent_bus import AgentBus

        bus = AgentBus(redis_url="redis://bad:6379")
        bus._redis = MagicMock()
        bus._redis.aclose = AsyncMock(side_effect=Exception("redis close fail"))
        await bus.close()


class TestReflectionCollectMemories:
    """Cover app/learning/reflection.py:219-231"""

    @pytest.mark.asyncio
    async def test_collect_recent_memories_empty(self) -> None:
        from datetime import datetime

        from app.learning.reflection import SelfReflectionEngine

        db = AsyncMock()
        db.execute.return_value = AsyncMock()
        db.execute.return_value.fetchall = MagicMock(return_value=[])
        engine = SelfReflectionEngine(db_session=db, workspace_id="ws1")
        memories = await engine._collect_recent_memories(datetime.now(UTC))
        assert memories == []


class TestHealthCheckApp:
    """Cover app/main.py:141-142 — health endpoint exception handler"""

    @pytest.mark.asyncio
    async def test_health_endpoint(self) -> None:
        from httpx import ASGITransport, AsyncClient

        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert "api" in data


class TestQuickTokenUserFound:
    """Cover app/routes/auth.py:53-55 — user found branch"""

    @pytest.mark.asyncio
    async def test_create_quick_token_user_found(self) -> None:
        from app.routes.auth import QuickTokenRequest, create_quick_token

        mock_request = MagicMock()
        body = QuickTokenRequest(sub="user1", workspace="ws1")
        with patch("app.routes.auth._get_session") as mock_gs:
            mock_db = AsyncMock()
            mock_gs.return_value.__aenter__.return_value = mock_db
            row = MagicMock()
            row.id = "found-id"
            row.role = "admin"
            mock_db.execute.return_value.fetchone.return_value = row
            with patch("app.routes.auth.create_access_token", return_value="tok"):
                result = await create_quick_token(mock_request, body)
                assert result.access_token == "tok"


class TestModelRouteGetHealth:
    """Cover app/routes/models.py:96-99 — no_model branch"""

    @pytest.mark.asyncio
    async def test_get_model_health_no_model(self) -> None:
        from app.routes.models import get_model_health

        mock_user = MagicMock()
        with patch("app.routes.models._get_session", new_callable=AsyncMock) as mock_gs:
            mock_db = AsyncMock()
            mock_gs.return_value.__aenter__.return_value = mock_db
            mock_rot = MagicMock()
            mock_rot.select_model = AsyncMock(return_value=None)
            with patch("app.utils.rotation_engine.RotationEngine", return_value=mock_rot):
                with patch("app.utils.model_discovery.ModelBenchmark") as mock_bc:
                    mock_bm = AsyncMock()
                    mock_bm.test = AsyncMock(return_value=(True, 0.5))
                    mock_bm.close = AsyncMock()
                    mock_bc.return_value = mock_bm
                    result = await get_model_health(mock_user)
                    assert hasattr(result, "data")


class TestSchedulerDiscoveryHealthTasks:
    """Cover app/scheduler.py:158-162, 256, 273-274"""

    @pytest.mark.asyncio
    async def test_execute_nightly_discovery(self) -> None:
        from app.scheduler import Scheduler

        sched = Scheduler()
        task = MagicMock()
        task.prompt = "__nightly_reflection__"
        with patch.object(sched, "_run_nightly_reflection", AsyncMock()) as mock_ref:
            await sched._execute_task(task)
            mock_ref.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_daily_discovery(self) -> None:
        from app.scheduler import Scheduler

        sched = Scheduler()
        task = MagicMock()
        task.prompt = "__daily_model_discovery__"
        with patch.object(sched, "_run_daily_model_discovery", AsyncMock()) as mock_disc:
            await sched._execute_task(task)
            mock_disc.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_health_check(self) -> None:
        from app.scheduler import Scheduler

        sched = Scheduler()
        task = MagicMock()
        task.prompt = "__model_health_check__"
        with patch.object(sched, "_run_model_health_check", AsyncMock()) as mock_hc:
            await sched._execute_task(task)
            mock_hc.assert_called_once()

    @pytest.mark.asyncio
    async def test_model_health_check_exception(self) -> None:
        from app.scheduler import Scheduler

        sched = Scheduler()
        with patch("app.scheduler.create_async_engine", side_effect=Exception("boom")):
            await sched._run_model_health_check()


class TestComputerUseDisabled:
    """Cover app/tools/computer_use.py:57-58"""

    @pytest.mark.asyncio
    async def test_initialize_disabled(self) -> None:
        from app.tools.computer_use import ComputerUseTools

        tools = ComputerUseTools(enabled=False)
        await tools.initialize()


class TestLLMClientOllamaMultimodal:
    """Cover app/utils/api_clients.py:95-100 — text extraction from multimodal"""

    @pytest.mark.asyncio
    async def test_complete_with_multimodal_extraction(self) -> None:
        from app.utils.api_clients import LLMClient

        client = LLMClient()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hello"},
                    {"type": "image_url", "image_url": {"url": "data:img/png;base64,x"}},
                ],
            }
        ]
        from app.utils.api_clients import LLMResponse

        with patch.object(client, "chat", AsyncMock()) as mock_chat:
            mock_chat.return_value = LLMResponse(content="ok", model="qwen2.5", provider="ollama")
            result = await client.complete("qwen2.5", "system", messages)
            assert result.content == "ok"


class TestAutoCorrectorFailurePath:
    """Cover app/utils/auto_corrector.py:93 — final return on max retries"""

    @pytest.mark.asyncio
    async def test_execute_failure_returns_correction_result(self) -> None:
        from app.utils.auto_corrector import AutoCorrector

        corrector = AutoCorrector(max_retries=0)
        result = await corrector.execute(code="bad code")
        assert not result.success


class TestLLMRouterNoDbUrl:
    """Cover app/utils/llm_router.py:43-44 — no DB URL branch"""

    @pytest.mark.asyncio
    async def test_reload_dynamic_no_db_url(self) -> None:
        from app.utils.llm_router import SmartLLMRouter

        router = SmartLLMRouter()
        with patch("app.utils.llm_router.get_settings") as mock_gs:
            mock_settings = MagicMock()
            mock_settings.resolved_database_url = ""
            mock_gs.return_value = mock_settings
            await router._reload_dynamic_models()
            assert router._dynamic_models == {}


class _AsyncSessionFactory:
    """Helper: creates an async context manager that yields the mock DB."""

    def __init__(self, mock_db: AsyncMock) -> None:
        self._mock_db = mock_db

    def __call__(self):
        return self

    async def __aenter__(self) -> AsyncMock:
        return self._mock_db

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        exc_tb: object | None = None,
    ) -> None:
        pass


class TestLLMRouterValueErrorBranches:
    """Cover app/utils/llm_router.py:51-52 — WorkType ValueError in _register_model_for_type"""

    @pytest.mark.asyncio
    async def test_dynamic_models_bad_work_type_values(self) -> None:
        from app.utils.llm_router import SmartLLMRouter

        router = SmartLLMRouter()
        with patch("app.utils.llm_router.get_settings") as mock_gs:
            mock_settings = MagicMock()
            mock_settings.resolved_database_url = "postgresql+asyncpg://u:p@h:5432/db"
            mock_gs.return_value = mock_settings
            mock_db = AsyncMock()
            mock_db.execute.return_value.fetchall.return_value = [
                ("m1", "model1", 128000, True, False, True, 20, 200, "bad_type", '["also_bad"]'),
            ]
            with patch("sqlalchemy.ext.asyncio.create_async_engine") as mock_ce:
                mock_engine = MagicMock()
                mock_ce.return_value = mock_engine
                mock_session_factory = _AsyncSessionFactory(mock_db)
                with patch(
                    "sqlalchemy.ext.asyncio.async_sessionmaker",
                    return_value=mock_session_factory,
                ):
                    await router._reload_dynamic_models()
                    assert router._dynamic_models is not None


class TestIntelligenceAddMemory:
    """Cover app/api/intelligence.py:61-83 — add_memory endpoint"""

    @pytest.mark.asyncio
    async def test_add_memory_success(self) -> None:
        from app.api.intelligence import add_memory

        mock_user = MagicMock()
        mock_db = AsyncMock()
        mock_record = AsyncMock(return_value="mem-uuid")
        with patch("app.api.intelligence._get_session", new_callable=AsyncMock) as mock_gs:
            mock_gs.return_value.__aenter__.return_value = mock_db
            with patch("app.api.intelligence.EpisodicMemory") as mock_em_cls:
                mock_em_cls.return_value.record = mock_record
                result = await add_memory(mock_user, "ws-1", {"task_type": "test"})
                assert result.data["id"] == "mem-uuid"


class TestAgentBusListenerMessage:
    """Cover app/bus/agent_bus.py:121-122 — listener happy path"""

    @pytest.mark.asyncio
    async def test_listener_receives_message(self) -> None:
        from app.bus.agent_bus import AgentBus

        bus = AgentBus(redis_url="redis://bad:6379")
        bus._redis = MagicMock()
        pubsub = AsyncMock()

        async def mock_listen():
            yield {"type": "subscribe", "data": 1}
            yield {"type": "message", "data": "hello"}

        pubsub.listen = mock_listen
        bus._redis.pubsub.return_value = pubsub
        queue = await bus.subscribe("test")
        import asyncio

        await asyncio.sleep(0.02)
        assert queue.qsize() == 1


class TestLLMClientOllamaMultimodalFallback:
    """Cover app/utils/api_clients.py:95-100 — text extraction from multimodal content"""

    @pytest.mark.asyncio
    async def test_complete_multimodal_ollama_fallback(self) -> None:
        from app.utils.api_clients import LLMClient

        client = LLMClient()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hello"},
                    {"type": "image_url", "image_url": {"url": "data:img/png;base64,abc"}},
                ],
            },
        ]
        with patch.object(client, "settings") as mock_settings:
            mock_settings.ollama_fallback_model = "qwen2.5:7b"
            mock_settings.ollama_base_url = "http://localhost:11434"
            with patch("httpx.AsyncClient") as mock_httpx:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"message": {"content": "ok"}, "model": "qwen2.5"}
                mock_httpx.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=mock_resp
                )
                result = await client.complete("qwen2.5:7b", "system", messages)
                assert result.content == "ok"


class TestSchedulerHealthCheckContinue:
    """Cover app/scheduler.py:256 — select_model returns None"""

    @pytest.mark.asyncio
    async def test_health_check_continue_on_no_model(self) -> None:
        from app.scheduler import Scheduler

        sched = Scheduler()
        with patch("app.scheduler.create_async_engine") as mock_ce:
            mock_engine = MagicMock()
            mock_ce.return_value = mock_engine
            with patch("app.scheduler.async_sessionmaker") as mock_sm:
                mock_db = AsyncMock()
                cm = MagicMock()
                cm.__aenter__ = AsyncMock(return_value=mock_db)
                cm.__aexit__ = AsyncMock()
                mock_sm.return_value = cm
                with patch("app.utils.rotation_engine.RotationEngine") as mock_re:
                    mock_rot = MagicMock()
                    mock_rot.select_model = AsyncMock(return_value=None)
                    mock_re.return_value = mock_rot
                    with patch("app.utils.model_discovery.ModelBenchmark") as mock_bc:
                        mock_bm = AsyncMock()
                        mock_bm.test = AsyncMock(return_value=(True, 0.5))
                        mock_bm.close = AsyncMock()
                        mock_bc.return_value = mock_bm
                        await sched._run_model_health_check()


class TestHealthCheckOllamaException:
    """Cover app/main.py:141-142 — health endpoint Ollama exception outer path"""

    @pytest.mark.asyncio
    async def test_health_ollama_outer_exception(self) -> None:
        from unittest.mock import Mock

        from app.main import health

        mock_s = Mock(
            spec=[
                "version",
                "resolved_database_url",
                "resolved_redis_url",
                "service_name",
                "otlp_enabled",
                "otlp_endpoint",
            ]
        )
        mock_s.version = "7.2.2"
        mock_s.resolved_database_url = "postgresql://u:p@localhost:5432/db"
        mock_s.resolved_redis_url = "memory://"
        mock_s.service_name = "agentos"
        mock_s.otlp_enabled = False
        mock_s.otlp_endpoint = ""
        with patch("app.main.settings", mock_s):
            result = await health()
            assert result["ollama"] == "error"


class TestLLMRouterCallOllamaMultimodal:
    """Cover app/utils/llm_router.py:279-284 — multimodal text extraction in _call_ollama"""

    @pytest.mark.asyncio
    async def test_call_ollama_multimodal_content(self) -> None:
        from app.utils.llm_router import SmartLLMRouter

        router = SmartLLMRouter()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hello"},
                    {"type": "image_url", "image_url": {"url": "data:img/png;base64,abc"}},
                ],
            },
        ]
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"message": {"content": "ok"}}
            mock_httpx.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await router._call_ollama(messages, temperature=0.7, max_tokens=1000)
            assert result["choices"][0]["message"]["content"] == "ok"


class TestContextEnricherTruncationBranches:
    """Cover app/learning/context_enricher.py:74, 102 — block truncation guards"""

    @pytest.mark.asyncio
    async def test_memories_block_truncated(self) -> None:
        from app.learning.context_enricher import ContextEnricher

        mock_db = MagicMock()
        enricher = ContextEnricher(mock_db)
        with patch.object(
            enricher.episodic,
            "recall_similar",
            AsyncMock(
                return_value=[
                    {
                        "quality_score": 0.9,
                        "prompt_summary": "Build API",
                        "strategy_used": "TDD",
                    },
                ]
            ),
        ):
            result = await enricher._build_memories_block(
                "code_gen",
                "ws-1",
                chars_used=1999,
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_skills_block_truncated(self) -> None:
        """Cover app/learning/context_enricher.py:102 — skills block truncated."""
        from app.learning.context_enricher import ContextEnricher

        mock_db = MagicMock()
        enricher = ContextEnricher(mock_db)
        with patch.object(
            enricher.skills,
            "find_relevant",
            AsyncMock(
                return_value=[
                    {
                        "name": "Test Skill",
                        "confidence_score": 0.85,
                        "description": "A test skill description",
                        "procedure": "Do step 1\nThen step 2",
                    },
                ]
            ),
        ):
            result = await enricher._build_skills_block(
                "test task",
                "ws-1",
                chars_used=1999,
            )
            assert result is None
