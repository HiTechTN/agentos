"""@Debugger — Runtime error analysis and fix suggestion sub-agent."""

from __future__ import annotations

import traceback

from pydantic import BaseModel

from app.agents.base import BaseAgent
from app.utils.api_clients import LLMClient

llm_client = LLMClient()


class DebugContext(BaseModel):
    error_type: str
    error_message: str
    traceback: str
    file: str | None = None
    line: int | None = None
    code_snippet: str | None = None


class DebugResult(BaseModel):
    root_cause: str
    explanation: str
    fix_suggestion: str
    code_patch: str | None = None
    related_files: list[str] = []
    confidence: float = 0.0


DEBUGGER_PROMPT = """Tu es @Debugger, un expert en débogage Python/FastAPI/LangGraph.
Analyse l'erreur fournie et retourne un JSON avec :
- root_cause : cause racine en 1 phrase
- explanation : explication technique détaillée
- fix_suggestion : correction recommandée
- code_patch : code corrigé si applicable
- related_files : fichiers potentiellement impactés
- confidence : score de confiance 0.0-1.0

Contexte projet : FastAPI + LangGraph + PostgreSQL + Redis.
RÉPONDRE UNIQUEMENT EN JSON, sans markdown.
"""


class DebuggerAgent(BaseAgent):
    name = "@Debugger"
    triggers = ["error", "exception", "traceback", "debug", "fix", "crash"]

    async def run(self, context: DebugContext) -> DebugResult:
        prompt = f"Erreur à analyser:\n{context.model_dump_json(indent=2)}"
        response = await llm_client.complete(
            model=type("M", (), {"__name__": "DebuggerAgent"})(),
            system=DEBUGGER_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return DebugResult.model_validate_json(response.content)

    @classmethod
    def from_exception(cls, exc: Exception) -> DebugContext:
        tb = traceback.extract_tb(exc.__traceback__)
        last_frame = tb[-1] if tb else None
        return DebugContext(
            error_type=type(exc).__name__,
            error_message=str(exc),
            traceback=traceback.format_exc(),
            file=last_frame.filename if last_frame else None,
            line=last_frame.lineno if last_frame else None,
        )
