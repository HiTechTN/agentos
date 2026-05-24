"""@Debugger sub-agent — runtime error analysis and fix proposals."""

from __future__ import annotations

import traceback
from typing import Any

from pydantic import BaseModel

from app.agents.base import BaseAgent


class DebugContext(BaseModel):
    error_type: str
    error_message: str
    traceback_str: str
    file: str | None = None
    line: int | None = None
    code_snippet: str | None = None


class DebugResult(BaseModel):
    root_cause: str
    explanation: str
    fix_suggestion: str
    code_patch: str | None = None
    related_files: list[str] = []
    confidence: float


_SYSTEM_PROMPT = """You are @Debugger, an expert in Python/FastAPI/LangGraph debugging.
Analyze the provided error and return ONLY a valid JSON object with these keys:
- root_cause (str): one-sentence root cause
- explanation (str): detailed technical explanation
- fix_suggestion (str): recommended fix
- code_patch (str | null): unified diff if applicable
- related_files (list[str]): potentially impacted files
- confidence (float): 0.0-1.0 confidence score
DO NOT wrap JSON in markdown. Return raw JSON only."""


class DebuggerAgent(BaseAgent):
    """@Debugger — auto-routed on error/exception/crash keywords."""

    name: str = "@Debugger"
    triggers: list[str] = [
        "error",
        "exception",
        "traceback",
        "debug",
        "fix",
        "crash",
        "fail",
    ]

    async def _run(
        self, action: str, params: dict[str, Any], session_id: str, trace_id: str
    ) -> Any:
        ctx = DebugContext(**params)
        return await self.run(ctx)

    async def run(self, context: DebugContext) -> DebugResult:
        """Analyze an error and return structured fix recommendations."""
        from app.utils.api_clients import LLMClient  # avoid circular import

        llm = LLMClient()
        prompt = f"Error to analyze:\n{context.model_dump_json(indent=2)}"
        response = await llm.complete(
            model="",
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return DebugResult.model_validate_json(response.content)

    @classmethod
    def from_exception(cls, exc: Exception) -> DebugContext:
        """Build a DebugContext from a live exception."""
        tb = traceback.extract_tb(exc.__traceback__)
        last = tb[-1] if tb else None
        return DebugContext(
            error_type=type(exc).__name__,
            error_message=str(exc),
            traceback_str=traceback.format_exc(),
            file=last.filename if last else None,
            line=last.lineno if last else None,
        )
