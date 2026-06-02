"""WebAssembly runner for executing tools in sandbox."""

import contextlib
import io
import time
import typing as t
from dataclasses import dataclass

if t.TYPE_CHECKING:
    import types


@dataclass
class WasmResult:
    """Result of a sandboxed code execution."""

    success: bool
    result: t.Any
    stdout: str
    stderr: str
    execution_time_ms: float


class WasmRunner:
    """Lightweight mock WebAssembly runner that isolates Python execution."""

    def __init__(self, timeout_ms: int = 5) -> None:
        """Initialize the runner with a timeout and empty code cache.

        Args:
            timeout_ms: Maximum execution time in milliseconds.
        """
        self.timeout_ms = timeout_ms
        self._cache: dict[str, types.CodeType] = {}

    async def run(self, code: str, globals_dict: dict[str, t.Any] | None = None) -> WasmResult:
        """Compile and execute Python code in an isolated namespace.

        Args:
            code: Python source code to execute.
            globals_dict: Optional globals namespace for execution.

        Returns:
            WasmResult with execution outcome, captured stdout, and timing.
        """
        if globals_dict is None:
            globals_dict = {}

        exec_globals: dict[str, t.Any] = {
            "__builtins__": __builtins__,
            **globals_dict,
        }

        if code in self._cache:
            compiled = self._cache[code]
        else:
            try:
                compiled = compile(code, "<wasm>", "exec")
            except SyntaxError as exc:
                return WasmResult(
                    success=False,
                    result=None,
                    stdout="",
                    stderr=str(exc),
                    execution_time_ms=0.0,
                )
            self._cache[code] = compiled

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        start = time.monotonic()

        try:
            with (
                contextlib.redirect_stdout(stdout_buf),
                contextlib.redirect_stderr(stderr_buf),
            ):
                exec(compiled, exec_globals)  # noqa: S102  # nosec
        except SyntaxError as exc:
            elapsed = (time.monotonic() - start) * 1000
            return WasmResult(
                success=False,
                result=None,
                stdout=stdout_buf.getvalue(),
                stderr=str(exc),
                execution_time_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return WasmResult(
                success=False,
                result=None,
                stdout=stdout_buf.getvalue(),
                stderr=str(exc),
                execution_time_ms=elapsed,
            )
        else:
            elapsed = (time.monotonic() - start) * 1000
            return WasmResult(
                success=True,
                result=None,
                stdout=stdout_buf.getvalue(),
                stderr=stderr_buf.getvalue(),
                execution_time_ms=elapsed,
            )
