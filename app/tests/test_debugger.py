from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.sub_agents.debugger import (
    DEBUGGER_PROMPT,
    DebugContext,
    DebuggerAgent,
    DebugResult,
    llm_client,
)


class TestDebugContext:
    def test_create_with_all_fields(self):
        ctx = DebugContext(
            error_type="ValueError",
            error_message="invalid value",
            traceback="Traceback (most recent call last):...",
            file="/path/to/file.py",
            line=42,
            code_snippet="x = int('abc')",
        )
        assert ctx.error_type == "ValueError"
        assert ctx.error_message == "invalid value"
        assert ctx.traceback
        assert ctx.file == "/path/to/file.py"
        assert ctx.line == 42
        assert ctx.code_snippet == "x = int('abc')"

    def test_optional_fields_default_to_none(self):
        ctx = DebugContext(error_type="E", error_message="m", traceback="t")
        assert ctx.file is None
        assert ctx.line is None
        assert ctx.code_snippet is None


class TestDebugResult:
    def test_create_with_all_fields(self):
        result = DebugResult(
            root_cause="Null pointer dereference",
            explanation="variable x is None when accessed",
            fix_suggestion="Add None check before accessing x",
            code_patch="if x is not None:\n    x.method()",
            related_files=["src/main.py", "src/utils.py"],
            confidence=0.95,
        )
        assert result.root_cause == "Null pointer dereference"
        assert result.confidence == 0.95
        assert len(result.related_files) == 2

    def test_optional_fields_default_to_empty(self):
        result = DebugResult(
            root_cause="rc", explanation="exp", fix_suggestion="fix"
        )
        assert result.code_patch is None
        assert result.related_files == []
        assert result.confidence == 0.0


class TestDebuggerAgent:
    @pytest.fixture
    def agent(self):
        original = DebuggerAgent.__abstractmethods__
        DebuggerAgent.__abstractmethods__ = frozenset()
        try:
            yield DebuggerAgent()
        finally:
            DebuggerAgent.__abstractmethods__ = original

    def test_name_constant(self):
        assert DebuggerAgent.name == "@Debugger"

    def test_triggers_defined(self):
        triggers = DebuggerAgent.triggers
        assert "error" in triggers
        assert "exception" in triggers
        assert "debug" in triggers
        assert "fix" in triggers
        assert "crash" in triggers
        assert "traceback" in triggers

    @pytest.mark.asyncio
    async def test_run_returns_parsed_debug_result(self, agent):
        context = DebugContext(
            error_type="ValueError",
            error_message="bad value",
            traceback="Traceback...",
        )
        mock_json = (
            '{"root_cause": "Type mismatch", '
            '"explanation": "Expected str, got int", '
            '"fix_suggestion": "Cast to str using str()", '
            '"code_patch": "str(x)", '
            '"related_files": ["app/main.py"], '
            '"confidence": 0.9}'
        )
        with patch.object(
            llm_client,
            "complete",
            AsyncMock(return_value=MagicMock(content=mock_json)),
            create=True,
        ):
            result = await agent.run(context)
            assert isinstance(result, DebugResult)
            assert result.root_cause == "Type mismatch"
            assert result.explanation == "Expected str, got int"
            assert result.fix_suggestion == "Cast to str using str()"
            assert result.code_patch == "str(x)"
            assert result.related_files == ["app/main.py"]
            assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_run_calls_llm_complete_with_context(self, agent):
        context = DebugContext(
            error_type="KeyError",
            error_message="missing key 'foo'",
            traceback="",
        )
        mock_json = (
            '{"root_cause": "x", "explanation": "y", "fix_suggestion": "z"}'
        )
        mock_complete = AsyncMock(return_value=MagicMock(content=mock_json))
        with patch.object(llm_client, "complete", mock_complete, create=True):
            await agent.run(context)
            mock_complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_invalid_json_raises(self, agent):
        context = DebugContext(
            error_type="E", error_message="m", traceback="t"
        )
        with patch.object(
            llm_client,
            "complete",
            AsyncMock(return_value=MagicMock(content="not valid json")),
            create=True,
        ):
            with pytest.raises(Exception):
                await agent.run(context)

    @pytest.mark.asyncio
    async def test_run_missing_root_cause_raises(self, agent):
        context = DebugContext(
            error_type="E", error_message="m", traceback="t"
        )
        with patch.object(
            llm_client,
            "complete",
            AsyncMock(return_value=MagicMock(content='{"explanation": "y"}')),
            create=True,
        ):
            with pytest.raises(Exception):
                await agent.run(context)

    def test_from_exception_with_traceback(self):
        try:
            raise ValueError("test error message")
        except ValueError as e:
            ctx = DebuggerAgent.from_exception(e)
            assert ctx.error_type == "ValueError"
            assert ctx.error_message == "test error message"
            assert ctx.traceback
            assert ctx.file is not None
            assert ctx.line is not None

    def test_from_exception_without_traceback(self):
        exc = Exception("fresh exception")
        ctx = DebuggerAgent.from_exception(exc)
        assert ctx.error_type == "Exception"
        assert ctx.error_message == "fresh exception"
        assert ctx.file is None
        assert ctx.line is None


class TestDebuggerPrompt:
    def test_prompt_is_french_and_contains_instructions(self):
        assert "Tu es @Debugger" in DEBUGGER_PROMPT
        assert "root_cause" in DEBUGGER_PROMPT
        assert "JSON" in DEBUGGER_PROMPT

    def test_prompt_mentions_project_context(self):
        assert "FastAPI" in DEBUGGER_PROMPT
        assert "LangGraph" in DEBUGGER_PROMPT
