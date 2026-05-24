"""Tests for @Debugger sub-agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.sub_agents.debugger import DebugContext, DebuggerAgent, DebugResult


@pytest.fixture()
def agent() -> DebuggerAgent:
    return DebuggerAgent()


@pytest.fixture()
def context() -> DebugContext:
    return DebugContext(
        error_type="ValueError",
        error_message="invalid literal for int()",
        traceback_str="Traceback...\nValueError: invalid literal for int()",
        file="app/agents/dev.py",
        line=42,
    )


class TestDebuggerAgentMeta:
    def test_name(self, agent: DebuggerAgent) -> None:
        assert agent.name == "@Debugger"

    def test_triggers_non_empty(self, agent: DebuggerAgent) -> None:
        assert len(agent.triggers) > 0
        assert "error" in agent.triggers


class TestFromException:
    def test_captures_error_type(self) -> None:
        try:
            raise ValueError("test error")
        except ValueError as exc:
            ctx = DebuggerAgent.from_exception(exc)
        assert ctx.error_type == "ValueError"
        assert "test error" in ctx.error_message

    def test_captures_file_and_line(self) -> None:
        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            ctx = DebuggerAgent.from_exception(exc)
        assert ctx.file is not None
        assert ctx.line is not None

    def test_no_traceback_returns_none_file(self) -> None:
        exc = ValueError("bare")
        ctx = DebuggerAgent.from_exception(exc)
        assert ctx.file is None


class TestDebuggerAgentRun:
    @pytest.mark.asyncio
    async def test_run_returns_debug_result(
        self, agent: DebuggerAgent, context: DebugContext
    ) -> None:
        mock_response = MagicMock()
        mock_response.content = """{
            "root_cause": "Type conversion failed",
            "explanation": "int() received non-numeric string",
            "fix_suggestion": "Validate input before conversion",
            "code_patch": null,
            "related_files": [],
            "confidence": 0.95
        }"""

        with patch("app.utils.api_clients.LLMClient") as mock_cls:
            instance = mock_cls.return_value
            instance.complete = AsyncMock(return_value=mock_response)
            result = await agent.run(context)

        assert isinstance(result, DebugResult)
        assert result.confidence == 0.95
        assert result.root_cause == "Type conversion failed"
