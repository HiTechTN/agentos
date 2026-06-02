"""Tests for the WasmRunner sandbox execution engine."""

import pytest

from app.sandbox.wasm_runner import WasmResult, WasmRunner


class TestWasmResult:
    """Dataclass field verification."""

    def test_result_dataclass(self) -> None:
        result = WasmResult(
            success=True,
            result="ok",
            stdout="out",
            stderr="err",
            execution_time_ms=12.5,
        )
        assert result.success is True
        assert result.result == "ok"
        assert result.stdout == "out"
        assert result.stderr == "err"
        assert result.execution_time_ms == 12.5


class TestWasmRunner:
    """Sandboxed code execution via WasmRunner."""

    @pytest.mark.asyncio
    async def test_run_success(self) -> None:
        runner = WasmRunner()
        result = await runner.run("x = 1 + 2")
        assert result.success is True
        assert result.stderr == ""

    @pytest.mark.asyncio
    async def test_run_syntax_error(self) -> None:
        runner = WasmRunner()
        result = await runner.run("if True print('x')")
        assert result.success is False
        assert result.result is None
        assert "invalid syntax" in result.stderr

    @pytest.mark.asyncio
    async def test_run_runtime_error(self) -> None:
        runner = WasmRunner()
        result = await runner.run("1 / 0")
        assert result.success is False
        assert "division by zero" in result.stderr

    @pytest.mark.asyncio
    async def test_run_captures_stdout(self) -> None:
        runner = WasmRunner()
        result = await runner.run("print('hello world')")
        assert result.success is True
        assert result.stdout == "hello world\n"

    @pytest.mark.asyncio
    async def test_run_captures_stderr(self) -> None:
        runner = WasmRunner()
        result = await runner.run("import sys; sys.stderr.write('err!')")
        assert result.success is True
        assert result.stderr == "err!"

    @pytest.mark.asyncio
    async def test_run_with_globals(self) -> None:
        runner = WasmRunner()
        result = await runner.run("print(x)", globals_dict={"x": 42})
        assert result.success is True
        assert result.stdout.strip() == "42"

    @pytest.mark.asyncio
    async def test_run_compilation_cache(self) -> None:
        runner = WasmRunner()
        code = "y = 2 ** 10"
        await runner.run(code)
        assert code in runner._cache
        await runner.run(code)
        assert len(runner._cache) == 1
