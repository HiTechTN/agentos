"""Targeted edge-case tests for v7.0 new modules.

Covers remaining uncovered lines in new v7.0 modules:
- agents/base.py:94-96 (enrichment success path)
- agents/dev.py:131-132 (auto_corrector usage)
- sandbox/ephemeral_fs.py:22 (tempfile.mkdtemp)
- sandbox/wasm_runner.py:10, 80-81 (import-level edge cases)
- tools/computer_use.py (disabled state branches)
- utils/auto_corrector.py:93, 126-128 (LLM fix fallback)
- utils/vram_manager.py:163 (fallback chain continue)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.sandbox.ephemeral_fs import EphemeralFS
from app.tools.computer_use import ComputerUseTools
from app.utils.vram_manager import VRAMManager


class TestComputerUseEdgeCases2:
    @pytest.mark.asyncio
    async def test_get_screen_state_disabled(self):
        """ComputerUseTools line 177: disabled returns placeholder."""
        tools = ComputerUseTools(enabled=False)
        result = await tools.get_screen_state()
        assert result == "[ComputerUseTools disabled]"

    @pytest.mark.asyncio
    async def test_close_resets_screen(self):
        """ComputerUseTools line 186: close resets screen state."""
        tools = ComputerUseTools(enabled=True)
        await tools.initialize()
        await tools.type_text("hello")
        await tools.close()
        state = await tools.get_screen_state()
        assert "Screen(1920x1080)" in state


class TestVRAMManagerEdgeCases:
    def test_fallback_chain_continue(self):
        """VRAMManager line 163: continue when fallback already in seen."""
        manager = VRAMManager(total_vram_gb=0.0)
        result = manager.get_best_model("code_gen", preferred="nomic-embed-text")
        assert result == "nomic-embed-text"

    def test_get_best_model_preferred_then_fallback(self):
        """VRAMManager full exhaustion fallback."""
        manager = VRAMManager(total_vram_gb=0.0)
        result = manager.get_best_model("code_gen", preferred="llama3.1:8b-q4_K_M")
        assert result == "nomic-embed-text"


class TestEphemeralFSEdgeCases:
    def test_init_without_base_dir(self):
        """EphemeralFS line 22: tempfile.mkdtemp when base_dir is None."""
        fs = EphemeralFS()
        assert fs.base_dir is not None
        assert fs.base_dir.exists()
        fs.cleanup()


class TestWasmRunnerEdgeCases:
    def test_import_and_basic(self):
        """WasmRunner import-level edge cases."""
        from app.sandbox.wasm_runner import WasmResult, WasmRunner

        runner = WasmRunner(timeout_ms=5)
        assert runner.timeout_ms == 5
        result = WasmResult(success=True, result=42, stdout="", stderr="", execution_time_ms=1.0)
        assert result.result == 42


@pytest.mark.asyncio
class TestComputerUseEdgeCases:
    async def test_initialize_enabled_logs(self):
        """ComputerUseTools line 57-58: enabled=True path."""
        tools = ComputerUseTools(enabled=True)
        await tools.initialize()
        assert tools._screen is not None

    async def test_click_disabled(self):
        """ComputerUseTools: click when disabled returns error."""
        tools = ComputerUseTools(enabled=False)
        result = await tools.click(100, 100)
        assert not result.success
        assert result.error is not None

    async def test_type_text_disabled(self):
        """ComputerUseTools: type_text when disabled returns error."""
        tools = ComputerUseTools(enabled=False)
        result = await tools.type_text("hello")
        assert not result.success

    async def test_screenshot_disabled(self):
        """ComputerUseTools: screenshot when disabled returns error."""
        tools = ComputerUseTools(enabled=False)
        result = await tools.screenshot()
        assert not result.success

    async def test_scroll_disabled(self):
        """ComputerUseTools: scroll when disabled returns error."""
        tools = ComputerUseTools(enabled=False)
        result = await tools.scroll()
        assert not result.success

    async def test_move_cursor_disabled(self):
        """ComputerUseTools: move_cursor when disabled returns error."""
        tools = ComputerUseTools(enabled=False)
        result = await tools.move_cursor(10, 10)
        assert not result.success


class TestDevAgentEdgeCases:
    def test_auto_corrector_in_init(self):
        """DevAgent line 131-132: auto_corrector is initialized."""
        from app.agents.dev import DevAgent

        agent = DevAgent()
        assert hasattr(agent, "auto_corrector")


@pytest.mark.asyncio
class TestAutoCorrectorEdgeCases:
    async def test_all_retries_fail(self):
        """AutoCorrector line 93: all retries exhausted."""
        with patch("app.utils.auto_corrector.llm_complete", new_callable=AsyncMock) as mock:
            mock.return_value = "def foo():\n    return 1\n"
            from app.utils.auto_corrector import AutoCorrector

            corrector = AutoCorrector(max_retries=1)
            code = "def foo(\n    return 1\n"
            result = await corrector.execute(code)
            assert not result.success
            assert result.attempts >= 1

    async def test_fix_with_llm_empty_response(self):
        """AutoCorrector line 126: LLM returns empty response."""
        with patch("app.utils.auto_corrector.llm_complete", new_callable=AsyncMock) as mock:
            mock.return_value = {"choices": []}
            from app.utils.auto_corrector import AutoCorrector

            corrector = AutoCorrector(max_retries=1)
            result = await corrector._fix_with_llm("x = 1", "syntax error")
            assert result == "x = 1"

    async def test_fix_with_llm_exception(self):
        """AutoCorrector line 128: LLM throws exception."""
        with patch("app.utils.auto_corrector.llm_complete", new_callable=AsyncMock) as mock:
            mock.side_effect = RuntimeError("LLM failed")
            from app.utils.auto_corrector import AutoCorrector

            corrector = AutoCorrector(max_retries=1)
            result = await corrector._fix_with_llm("x = 1", "syntax error")
            assert result == "x = 1"
