"""Tests for the AutoCorrector LLM-driven retry-fix loop."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.utils.auto_corrector import AutoCorrector, CorrectionResult

VALID_CODE = "x = 1"
SYNTAX_ERROR_CODE = "x = "
FIXED_CODE = "x = 42"


class TestAutoCorrectorExecute:
    @pytest.mark.asyncio
    async def test_execute_valid_code(self) -> None:
        corrector = AutoCorrector(max_retries=3)
        result = await corrector.execute(VALID_CODE)

        assert result.success is True
        assert result.code == VALID_CODE
        assert result.attempts == 1
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_execute_syntax_error_fixed(self) -> None:
        mock_response: dict = {"choices": [{"message": {"content": FIXED_CODE}}]}

        corrector = AutoCorrector(max_retries=3)
        with patch("app.utils.auto_corrector.llm_complete", AsyncMock(return_value=mock_response)):
            result = await corrector.execute(SYNTAX_ERROR_CODE)

        assert result.success is True
        assert result.code == FIXED_CODE
        assert result.attempts == 2
        assert len(result.errors) == 1
        assert "SyntaxError" in result.errors[0]

    @pytest.mark.asyncio
    async def test_execute_all_retries_fail(self) -> None:
        mock_response: dict = {"choices": [{"message": {"content": SYNTAX_ERROR_CODE}}]}

        corrector = AutoCorrector(max_retries=3)
        with patch("app.utils.auto_corrector.llm_complete", AsyncMock(return_value=mock_response)):
            result = await corrector.execute(SYNTAX_ERROR_CODE)

        assert result.success is False
        assert result.attempts == 3
        assert len(result.errors) == 3

    @pytest.mark.asyncio
    async def test_execute_max_retries_respected(self) -> None:
        mock_response: dict = {"choices": [{"message": {"content": SYNTAX_ERROR_CODE}}]}

        call_count: int = 0

        async def counting_llm(*args: object, **kwargs: object) -> dict:
            nonlocal call_count
            call_count += 1
            return mock_response

        corrector = AutoCorrector(max_retries=1)
        with patch("app.utils.auto_corrector.llm_complete", side_effect=counting_llm):
            result = await corrector.execute(SYNTAX_ERROR_CODE)

        assert result.success is False
        assert result.attempts == 1
        # On last attempt _fix_with_llm is not called (attempt == max_retries)
        assert call_count == 0

    @pytest.mark.asyncio
    async def test_correction_result_success(self) -> None:
        result = CorrectionResult(success=True, code=VALID_CODE, attempts=1)

        assert result.success is True
        assert isinstance(result.code, str)

    @pytest.mark.asyncio
    async def test_correction_result_failure(self) -> None:
        result = CorrectionResult(
            success=False,
            code=SYNTAX_ERROR_CODE,
            attempts=3,
            errors=["SyntaxError: invalid syntax (line 1)"],
        )

        assert result.success is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_correction_result_tracks_attempts(self) -> None:
        attempts = [1, 2, 3]
        for attempt in attempts:
            result = CorrectionResult(
                success=attempt < 3,
                code="x = 1",
                attempts=attempt,
            )
            assert result.attempts == attempt
