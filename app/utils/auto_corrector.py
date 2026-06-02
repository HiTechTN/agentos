"""Auto-corrector that wraps sandbox execution with a retry-fix LLM loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.utils.api_clients import llm_complete
from app.utils.llm_router import WorkType


@dataclass
class CorrectionResult:
    """Result of an auto-correction attempt.

    Attributes:
        success: Whether the code eventually passed.
        code: The final (possibly corrected) code.
        attempts: Number of attempts made.
        errors: List of error messages encountered.
    """

    success: bool
    code: str
    attempts: int = 1
    errors: list[str] = field(default_factory=list)


class AutoCorrector:
    """Wraps code execution with an LLM-driven retry-fix loop.

    Attributes:
        max_retries: Maximum number of correction attempts.
    """

    _FIX_PROMPT: str = (
        "Fix the following Python code. The error was:\n{error}\n\n"
        "Code:\n{code}\n\nReturn ONLY the fixed code, no explanation."
    )

    def __init__(self, max_retries: int = 3) -> None:
        """Initialise the auto-corrector.

        Args:
            max_retries: Maximum number of LLM fix attempts. Defaults to 3.
        """
        self.max_retries: int = max_retries

    async def execute(
        self,
        code: str,
        work_type: str = "DEBUG",
        agent_name: str = "auto_corrector",
    ) -> CorrectionResult:
        """Execute code with automatic LLM-based error correction.

        Simulates sandbox execution by checking for syntax errors via
        ``compile()``. If a syntax error is found, the error is sent to
        an LLM for a fix and the corrected code is retried.

        Args:
            code: The Python code snippet to execute and potentially fix.
            work_type: The ``WorkType`` string for LLM routing.
            agent_name: Agent name passed to the LLM for logging.

        Returns:
            A ``CorrectionResult`` with the final outcome.
        """
        errors: list[str] = []

        for attempt in range(1, self.max_retries + 1):
            syntax_error = self._check_syntax(code)
            if syntax_error is None:
                return CorrectionResult(
                    success=True,
                    code=code,
                    attempts=attempt,
                    errors=errors,
                )

            errors.append(syntax_error)

            if attempt < self.max_retries:
                code = await self._fix_with_llm(code, syntax_error)
            else:
                return CorrectionResult(
                    success=False,
                    code=code,
                    attempts=attempt,
                    errors=errors,
                )

        return CorrectionResult(
            success=False,
            code=code,
            attempts=self.max_retries,
            errors=errors,
        )

    async def _fix_with_llm(self, code: str, error: str) -> str:
        """Send the broken code and error to an LLM and return the fixed code.

        Args:
            code: The Python code that failed.
            error: The error message from the sandbox execution.

        Returns:
            The LLM-generated fixed code, or the original code if the LLM
            call fails.
        """
        prompt = self._FIX_PROMPT.format(code=code, error=error)
        try:
            response: dict[str, Any] = await llm_complete(
                prompt=prompt,
                system="You are a Python code fixer. Return only fixed code.",
                agent_name="auto_corrector",
                work_type=WorkType.DEBUG,
            )
            fixed: str = ""
            choices = response.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                fixed = message.get("content", "")
            if fixed.strip():
                return fixed.strip().removeprefix("```python").removesuffix("```").strip()
            return code
        except Exception:
            return code

    @staticmethod
    def _check_syntax(code: str) -> str | None:
        """Check Python code for syntax errors using ``compile()``.

        Args:
            code: The Python code string to check.

        Returns:
            The error message string if a syntax error is found, or None.
        """
        try:
            compile(code, "<sandbox>", "exec")
            return None
        except SyntaxError as exc:
            msg = exc.msg or "Unknown syntax error"
            line_info = f" (line {exc.lineno})" if exc.lineno else ""
            text_info = f": {exc.text.strip()}" if exc.text else ""
            return f"SyntaxError: {msg}{line_info}{text_info}"
