import json
from typing import Any

from app.agents.base import AgentError, BaseAgent, ToolResult
from app.utils.auto_corrector import AutoCorrector
from app.utils.hitl_gateway import HITLPendingError


class DevAgent(BaseAgent):
    name = "dev"
    model = "anthropic/claude-sonnet-20241022"

    HITL_ACTIONS = {"deploy"}

    def __init__(self) -> None:
        super().__init__()
        self.auto_corrector = AutoCorrector(max_retries=3)

    async def _run(
        self,
        action: str,
        params: dict[str, Any],
        session_id: str,
        trace_id: str,
        attachments: list[dict[str, str]] | None = None,
    ) -> Any:
        if action in self.HITL_ACTIONS:
            try:
                details = {"action": action, "params": params, "agent": self.name}
                await self._require_hitl(session_id, action, details)
            except HITLPendingError:
                raise

        tool_map = {
            "scaffold": self._scaffold,
            "test": self._run_tests,
            "lint": self._run_lint,
            "deploy": self._deploy,
            "analyze": self._analyze,
        }

        handler = tool_map.get(action)
        if not handler:
            raise AgentError("UNKNOWN_ACTION", f"Unknown action: {action}")

        return await handler(params, session_id, trace_id)

    async def _scaffold(self, params: dict[str, Any], session_id: str, trace_id: str) -> ToolResult:
        prompt = params.get("prompt", "Scaffold a new project structure")
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"""Scaffold a project structure for:
{prompt}

Generate code for: README.md (description), .github/workflows/ci.yml (GitHub Actions),
.gitlab-ci.yml (GitLab CI), setup.py/pyproject.toml, requirements.txt, src/ directory.
Return the file tree and brief descriptions.""",
            },
        ]
        content = await self._llm_call(messages)
        return ToolResult(success=True, data={"plan": content})

    async def _run_tests(
        self, params: dict[str, Any], session_id: str, trace_id: str
    ) -> ToolResult:
        framework = params.get("framework", "pytest")
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"""Write {framework} tests for:
{json.dumps(params, indent=2)}

Generate test files with proper fixtures, mocks, and assertions.
Cover edge cases and error handling.""",
            },
        ]
        content = await self._llm_call(messages)
        return ToolResult(success=True, data={"tests": content})

    async def _run_lint(self, params: dict[str, Any], session_id: str, trace_id: str) -> ToolResult:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"""Review and fix linting for the codebase at:
{json.dumps(params, indent=2)}

Configure ruff and mypy. List all issues found and fixes applied.""",
            },
        ]
        content = await self._llm_call(messages)
        return ToolResult(success=True, data={"lint_report": content})

    async def _deploy(self, params: dict[str, Any], session_id: str, trace_id: str) -> ToolResult:
        target = params.get("target", "staging")
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"""Deploy the project to {target}:
{json.dumps(params, indent=2)}

Generate deployment script, verify health checks, configure environment variables.
Note: HITL approval was obtained for this deployment.""",
            },
        ]
        content = await self._llm_call(messages)
        return ToolResult(success=True, data={"deployment": content, "target": target})

    async def _analyze(self, params: dict[str, Any], session_id: str, trace_id: str) -> ToolResult:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"""Analyze the following code or requirements:
{json.dumps(params, indent=2)}

Provide architecture analysis, tech stack recommendations, and potential issues.""",
            },
        ]
        content = await self._llm_call(messages)
        return ToolResult(success=True, data={"analysis": content})

    async def _correct_code(self, code: str) -> str:
        """Fix Python code using the auto-corrector's syntax check + LLM repair loop.

        Args:
            code: The Python code to check and fix.

        Returns:
            The corrected code (or original if no fix needed).
        """
        result = await self.auto_corrector.execute(code)
        return result.code
