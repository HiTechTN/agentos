from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import AgentError, BaseAgent, ToolResult
from app.utils.hitl_gateway import HITLPendingError


class _MinimalAgent(BaseAgent):
    name = "test"
    model = "test-model"

    async def _run(
        self, action: str, params: dict[str, Any], session_id: str, trace_id: str
    ) -> Any:
        return {"action": action, "params": params, "session_id": session_id, "trace_id": trace_id}


@pytest.fixture
def agent() -> Generator[Any]:
    with (
        patch("app.agents.base.LLMClient") as mock_llm_cls,
        patch("app.agents.base.get_hitl_gateway") as mock_hitl_getter,
    ):
        mock_llm = mock_llm_cls.return_value
        mock_llm.chat = AsyncMock(return_value=MagicMock(content="llm response"))
        mock_llm.chat_with_model_selection = AsyncMock(
            return_value=MagicMock(content="routed response")
        )

        mock_hitl = AsyncMock()
        mock_hitl.request_approval = AsyncMock(return_value={"approved": True})
        mock_hitl_getter.return_value = mock_hitl

        a = _MinimalAgent()
        yield a


class TestAgentError:
    def test_stores_attributes(self) -> None:
        err = AgentError("ERR_CODE", "human message", "detail string")
        assert err.code == "ERR_CODE"
        assert err.detail == "detail string"
        assert str(err) == "human message"

    def test_is_exception_subclass(self) -> None:
        assert issubclass(AgentError, Exception)


class TestToolResult:
    def test_stores_attributes(self) -> None:
        result = ToolResult(success=True, data={"key": "val"}, message="done")
        assert result.success is True
        assert result.data == {"key": "val"}
        assert result.message == "done"

    def test_failure_result(self) -> None:
        result = ToolResult(success=False, data=None, message="error occurred")
        assert result.success is False
        assert result.data is None
        assert result.message == "error occurred"


class TestLoadPrompts:
    def test_matching_key_overrides_system_prompt(self) -> None:
        with (
            patch("builtins.open", MagicMock()),
            patch(
                "app.agents.base.yaml.safe_load",
                return_value={"test": {"system": "Custom override"}},
            ),  # noqa: E501
            patch("app.agents.base.LLMClient"),
            patch("app.agents.base.get_hitl_gateway"),
        ):
            a = _MinimalAgent()
            assert a.system_prompt == "Custom override"

    def test_missing_key_keeps_default(self) -> None:
        with (
            patch("builtins.open", MagicMock()),
            patch(
                "app.agents.base.yaml.safe_load", return_value={"other_agent": {"system": "Nope"}}
            ),  # noqa: E501
            patch("app.agents.base.LLMClient"),
            patch("app.agents.base.get_hitl_gateway"),
        ):
            a = _MinimalAgent()
            assert a.system_prompt == ""

    def test_file_not_found_caught_silently(self) -> None:
        with (
            patch("builtins.open", side_effect=FileNotFoundError("no such file")),
            patch("app.agents.base.LLMClient"),
            patch("app.agents.base.get_hitl_gateway"),
        ):
            a = _MinimalAgent()
            assert a.system_prompt == ""

    def test_invalid_yaml_caught_silently(self) -> None:
        with (
            patch("builtins.open", MagicMock()),
            patch("app.agents.base.yaml.safe_load", side_effect=Exception("bad yaml")),
            patch("app.agents.base.LLMClient"),
            patch("app.agents.base.get_hitl_gateway"),
        ):
            a = _MinimalAgent()
            assert a.system_prompt == ""


class TestEffectiveModel:
    def test_default_model(self, agent: Any) -> None:
        assert agent.effective_model == "test-model"

    def test_env_override_takes_precedence(self, agent: Any) -> None:
        mock_settings = MagicMock()
        mock_settings.test_agent_model = "override-model"
        with patch.object(agent, "settings", mock_settings):
            assert agent.effective_model == "override-model"

    def test_empty_override_falls_back_to_model(self, agent: Any) -> None:
        mock_settings = MagicMock()
        mock_settings.test_agent_model = ""
        with patch.object(agent, "settings", mock_settings):
            assert agent.effective_model == "test-model"


class TestExecute:
    async def test_happy_path_default_action(self, agent: Any) -> None:
        result = await agent.execute(
            {"params": {"prompt": "hello"}}, session_id="s1", trace_id="t1"
        )  # noqa: E501
        assert result["success"] is True
        assert result["agent"] == "test"
        assert result["action"] == "execute"
        assert result["result"]["action"] == "execute"
        assert result["result"]["params"]["prompt"] == "hello"
        assert result["result"]["session_id"] == "s1"
        assert result["result"]["trace_id"] == "t1"

    async def test_happy_path_with_action(self, agent: Any) -> None:
        result = await agent.execute(
            {"action": "analyze", "params": {"prompt": "test"}},
            session_id="s2",
            trace_id="t2",
        )
        assert result["success"] is True
        assert result["action"] == "analyze"
        assert result["result"]["action"] == "analyze"

    async def test_rag_context_appended_when_present(self, agent: Any) -> None:
        with patch.object(agent, "_retrieve_context", AsyncMock(return_value="relevant context")):
            result = await agent.execute({"action": "analyze", "params": {"prompt": "test"}})
            assert result["success"] is True
            assert result["result"]["params"]["rag_context"] == "relevant context"

    async def test_rag_context_skipped_when_empty(self, agent: Any) -> None:
        with patch.object(agent, "_retrieve_context", AsyncMock(return_value="")):
            result = await agent.execute({"action": "analyze", "params": {"prompt": "test"}})
            assert result["success"] is True
            assert "rag_context" not in result["result"]["params"]

    async def test_re_raises_hitl_pending_error(self, agent: Any) -> None:
        agent._run = AsyncMock(side_effect=HITLPendingError("aid-123", "deploy"))
        with pytest.raises(HITLPendingError) as exc:
            await agent.execute({"action": "deploy", "params": {}})
        assert exc.value.approval_id == "aid-123"

    async def test_agent_error_returns_error_dict(self, agent: Any) -> None:
        agent._run = AsyncMock(side_effect=AgentError("CUSTOM_ERR", "custom message", "detail"))
        result = await agent.execute({"action": "analyze", "params": {}})
        assert result["success"] is False
        assert result["error"]["code"] == "CUSTOM_ERR"
        assert result["error"]["message"] == "custom message"

    async def test_llm_unavailable_returns_degraded(self, agent: Any) -> None:
        from app.utils.api_clients import LLMUnavailableError

        agent._run = AsyncMock(side_effect=LLMUnavailableError("all providers down"))
        result = await agent.execute({"action": "analyze", "params": {}})
        assert result["success"] is False
        assert result["degraded"] is True
        assert result["error"]["code"] == "LLM_UNAVAILABLE"

    async def test_unexpected_exception_returns_error(self, agent: Any) -> None:
        agent._run = AsyncMock(side_effect=ValueError("something went wrong"))
        result = await agent.execute({"action": "analyze", "params": {}})
        assert result["success"] is False
        assert result["error"]["code"] == "UNEXPECTED"
        assert "something went wrong" in result["error"]["message"]


class TestRetrieveContext:
    @pytest.mark.asyncio
    async def test_empty_results_returns_empty_string(self, agent: Any) -> None:
        with patch("app.memory.vector_store.get_vector_store") as mock_get:
            mock_vs = AsyncMock()
            mock_vs.search = AsyncMock(return_value=[])
            mock_get.return_value = mock_vs
            result = await agent._retrieve_context(
                "sess-1", {"action": "test", "params": {"prompt": "hi"}}
            )  # noqa: E501
            assert result == ""

    @pytest.mark.asyncio
    async def test_results_with_content_returns_joined_context(self, agent: Any) -> None:
        with patch("app.memory.vector_store.get_vector_store") as mock_get:
            mock_vs = AsyncMock()
            mock_vs.search = AsyncMock(
                return_value=[
                    {"content": "first document content"},
                    {"content": "second document content"},
                ]
            )
            mock_get.return_value = mock_vs
            result = await agent._retrieve_context(
                "sess-1", {"action": "test", "params": {"prompt": "hi"}}
            )  # noqa: E501
            assert "first document content" in result
            assert "second document content" in result
            assert "\n---\n" in result

    @pytest.mark.asyncio
    async def test_results_with_missing_content_returns_empty(self, agent: Any) -> None:
        with patch("app.memory.vector_store.get_vector_store") as mock_get:
            mock_vs = AsyncMock()
            mock_vs.search = AsyncMock(return_value=[{"id": "1", "content": None}])
            mock_get.return_value = mock_vs
            result = await agent._retrieve_context(
                "sess-1", {"action": "test", "params": {"prompt": "hi"}}
            )  # noqa: E501
            assert result == ""

    @pytest.mark.asyncio
    async def test_exception_is_caught_returns_empty(self, agent: Any) -> None:
        with patch("app.memory.vector_store.get_vector_store") as mock_get:
            mock_vs = AsyncMock()
            mock_vs.search = AsyncMock(side_effect=RuntimeError("db down"))
            mock_get.return_value = mock_vs
            result = await agent._retrieve_context(
                "sess-1", {"action": "test", "params": {"prompt": "hi"}}
            )  # noqa: E501
            assert result == ""

    @pytest.mark.asyncio
    async def test_content_truncated_to_500_chars(self, agent: Any) -> None:
        long_content = "x" * 1000
        with patch("app.memory.vector_store.get_vector_store") as mock_get:
            mock_vs = AsyncMock()
            mock_vs.search = AsyncMock(return_value=[{"content": long_content}])
            mock_get.return_value = mock_vs
            result = await agent._retrieve_context(
                "sess-1", {"action": "test", "params": {"prompt": "hi"}}
            )  # noqa: E501
            assert result == long_content[:500]

    @pytest.mark.asyncio
    async def test_single_result_no_separator_needed(self, agent: Any) -> None:
        with patch("app.memory.vector_store.get_vector_store") as mock_get:
            mock_vs = AsyncMock()
            mock_vs.search = AsyncMock(return_value=[{"content": "single doc"}])
            mock_get.return_value = mock_vs
            result = await agent._retrieve_context(
                "sess-1", {"action": "test", "params": {"prompt": "hi"}}
            )  # noqa: E501
            assert result == "single doc"
            assert "---" not in result


class TestLLMCall:
    @pytest.mark.asyncio
    async def test_llm_call_returns_content(self, agent: Any) -> None:
        agent.llm.chat = AsyncMock(return_value=MagicMock(content="response text"))
        result = await agent._llm_call([{"role": "user", "content": "hi"}], temperature=0.5)
        assert result == "response text"
        agent.llm.chat.assert_awaited_once_with(
            model=agent.effective_model,
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.5,
        )

    @pytest.mark.asyncio
    async def test_llm_call_default_temperature(self, agent: Any) -> None:
        agent.llm.chat = AsyncMock(return_value=MagicMock(content="resp"))
        result = await agent._llm_call([{"role": "user", "content": "hi"}])
        assert result == "resp"
        agent.llm.chat.assert_awaited_once_with(
            model=agent.effective_model,
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.7,
        )


class TestLLMCallRouted:
    @pytest.mark.asyncio
    async def test_returns_content(self, agent: Any) -> None:
        agent.llm.chat_with_model_selection = AsyncMock(
            return_value=MagicMock(content="routed response")
        )
        result = await agent._llm_call_routed(
            "code", [{"role": "user", "content": "write code"}], temperature=0.3
        )  # noqa: E501
        assert result == "routed response"
        agent.llm.chat_with_model_selection.assert_awaited_once_with(
            task_type="code",
            messages=[{"role": "user", "content": "write code"}],
            temperature=0.3,
        )

    @pytest.mark.asyncio
    async def test_default_temperature(self, agent: Any) -> None:
        agent.llm.chat_with_model_selection = AsyncMock(return_value=MagicMock(content="routed"))
        result = await agent._llm_call_routed("analysis", [{"role": "user", "content": "analyze"}])
        assert result == "routed"
        agent.llm.chat_with_model_selection.assert_awaited_once_with(
            task_type="analysis",
            messages=[{"role": "user", "content": "analyze"}],
            temperature=0.7,
        )


class TestRequireHITL:
    @pytest.mark.asyncio
    async def test_requests_approval_with_correct_args(self, agent: Any) -> None:
        result = await agent._require_hitl("session-1", "deploy", {"target": "prod"})
        agent._hitl.request_approval.assert_awaited_once_with(
            session_id="session-1",
            agent_name="test",
            action="deploy",
            details={"target": "prod"},
        )
        assert result == {"approved": True}

    @pytest.mark.asyncio
    async def test_passes_through_hitl_error(self, agent: Any) -> None:
        agent._hitl.request_approval = AsyncMock(side_effect=HITLPendingError("aid-99", "deploy"))
        with pytest.raises(HITLPendingError) as exc:
            await agent._require_hitl("s1", "deploy", {})
        assert exc.value.approval_id == "aid-99"
