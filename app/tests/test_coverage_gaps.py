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
