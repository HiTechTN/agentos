"""Tests for DevAgent — code generation and autocorrection."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.agents.dev import DevAgent
from app.utils.auto_corrector import CorrectionResult


@pytest.fixture
def dev_agent() -> Generator[Any]:
    with (
        patch("app.agents.base.LLMClient") as mock_llm_cls,
        patch("app.agents.base.get_hitl_gateway") as mock_hitl_getter,
    ):
        mock_llm = mock_llm_cls.return_value
        mock_llm.chat = AsyncMock(return_value=Mock(content="llm response"))
        mock_llm.chat_with_model_selection = AsyncMock(return_value=Mock(content="routed response"))

        mock_hitl = AsyncMock()
        mock_hitl.request_approval = AsyncMock(return_value={"approved": True})
        mock_hitl_getter.return_value = mock_hitl

        a = DevAgent()
        yield a


class TestDevAgentCorrectCode:
    @pytest.mark.asyncio
    async def test_correct_code_returns_corrected_result(self, dev_agent: Any) -> None:
        code = "x = 1"
        mock_result = CorrectionResult(code="x = 2", success=True, errors=[])
        with patch.object(
            dev_agent.auto_corrector, "execute", new=AsyncMock(return_value=mock_result)
        ):
            result = await dev_agent._correct_code(code)
        assert result == "x = 2"

    @pytest.mark.asyncio
    async def test_correct_code_returns_original_on_success(self, dev_agent: Any) -> None:
        code = "y = 42"
        mock_result = CorrectionResult(code=code, success=True, errors=[])
        with patch.object(
            dev_agent.auto_corrector, "execute", new=AsyncMock(return_value=mock_result)
        ):
            result = await dev_agent._correct_code(code)
        assert result == code

    @pytest.mark.asyncio
    async def test_execute_analyze_action(self, dev_agent: Any) -> None:
        result = await dev_agent.execute(
            {"action": "analyze", "params": {"prompt": "analyze this code"}},
        )
        assert result["success"] is True
        assert result["action"] == "analyze"

    @pytest.mark.asyncio
    async def test_execute_unknown_action_returns_error(self, dev_agent: Any) -> None:
        result = await dev_agent.execute(
            {"action": "unknown_action", "params": {}},
        )
        assert result["success"] is False
        assert result["error"]["code"] == "UNKNOWN_ACTION"
