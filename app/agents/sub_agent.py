"""Sub-agent system: @Verifier, @Explorer, @CodeReviewer, @Planner + custom sub-agents."""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.utils.api_clients import LLMClient
from app.utils.logging import get_logger

logger = get_logger("sub_agent")


class ToolSet(Protocol):
    async def run_command(self, cmd: str, timeout: int = 30) -> str: ...
    async def read_file(self, path: str) -> str: ...
    async def search_files(self, pattern: str) -> list[str]: ...
    async def grep_content(self, pattern: str, path: str = ".") -> list[dict[str, Any]]: ...


@dataclass
class SubAgentConfig:
    name: str
    system_prompt: str
    model: str = ""
    tools: list[str] = field(default_factory=lambda: ["read", "search", "grep", "bash"])
    temperature: float = 0.2
    max_tokens: int = 4096
    auto_route: bool = True


BUILTIN_SUB_AGENTS: dict[str, SubAgentConfig] = {
    "debugger": SubAgentConfig(
        name="Debugger",
        system_prompt="""You are @Debugger, an expert Python/FastAPI/LangGraph debugger.
Analyze errors and return JSON: {"root_cause":"","explanation":"","fix_suggestion":"","code_patch":null,"related_files":[],"confidence":0.0}""",  # noqa: E501
        model="anthropic/claude-sonnet-20241022",
        temperature=0.1,
    ),
    "planner": SubAgentConfig(
        name="Planner",
        system_prompt="""You are a expert software architect. Analyze requirements and produce structured plans.
Output JSON: {"phases": [{"name":"","description":"","tasks":[{"id":"","title":"","description":"","agent":"","dependencies":[],"estimated_minutes":0}],"order":0}], "risks":[], "stack":"","architecture_summary":""}""",  # noqa: E501
        model="anthropic/claude-sonnet-20241022",
        temperature=0.1,
    ),
    "verifier": SubAgentConfig(
        name="Verifier",
        system_prompt="""You are a QA expert. Verify code quality, run validation checks.
Check: lint, type safety, test coverage, security, edge cases.
Output: {"passed":bool,"issues":[{"severity":"high|medium|low","file":"","line":0,"message":"","suggestion":""}],"coverage_estimate":"","summary":""}""",  # noqa: E501
        model="openai/gpt-4o-2024-11-20",
        temperature=0.1,
    ),
    "explorer": SubAgentConfig(
        name="Explorer",
        system_prompt="""You are a codebase explorer. Search, analyze, and summarize code.
Understand architecture, find relevant files, trace dependencies.
Output: {"files_found":[],"architecture":"","dependencies":[],"relevance_scores":{},"summary":""}""",  # noqa: E501
        model="openai/gpt-4o-2024-11-20",
        temperature=0.2,
    ),
    "code_reviewer": SubAgentConfig(
        name="CodeReviewer",
        system_prompt="""You are a senior engineer doing code review.
Check: security, performance, architecture, style, edge cases, error handling.
Output: {"approved":bool,"security_issues":[],"perf_issues":[],"arch_issues":[],"style_notes":[],"suggestions":[],"summary":""}""",  # noqa: E501
        model="anthropic/claude-sonnet-20241022",
        temperature=0.1,
    ),
}


class SubAgent:
    def __init__(self, config: SubAgentConfig, tools: ToolSet | None = None):
        self.config = config
        self.tools = tools
        self.llm: LLMClient = LLMClient()
        self.logger = get_logger(f"subagent_{config.name}")

    async def run(self, task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        self.logger.log_action(
            "sub_agent", "run", "started", details={"name": self.config.name, "task": task[:100]}
        )
        messages: list[dict[str, Any]] = [{"role": "system", "content": self.config.system_prompt}]
        if context:
            messages.append(
                {
                    "role": "system",
                    "content": f"Context:\n{json.dumps(context, default=str)[:4000]}",
                }
            )
        messages.append({"role": "user", "content": task})

        model = self.config.model or "openai/gpt-4o-2024-11-20"
        response = await self.llm.chat(model, messages, temperature=self.config.temperature)

        try:
            cleaned = response.content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            result: dict[str, Any] = json.loads(cleaned)
        except (json.JSONDecodeError, AttributeError):
            result = {"raw_response": response.content, "parsed": False}

        self.logger.log_action("sub_agent", "run", "completed", details={"name": self.config.name})
        return result


def get_sub_agent(name: str, tools: ToolSet | None = None) -> SubAgent | None:
    config = BUILTIN_SUB_AGENTS.get(name)
    if config:
        return SubAgent(config, tools)
    custom_path = os.path.expanduser(f"~/.agentos/subagents/{name}.md")
    if os.path.exists(custom_path):
        config = _load_custom_config(custom_path)
        if config:
            return SubAgent(config, tools)
    return None


def _load_custom_config(path: str) -> SubAgentConfig | None:
    try:
        with open(path) as f:
            content = f.read()
        import yaml  # type: ignore[import-untyped]

        parts = content.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1])
            return SubAgentConfig(
                name=meta.get("name", os.path.basename(path).replace(".md", "")),
                system_prompt=parts[2].strip(),
                model=meta.get("model", ""),
                tools=meta.get("tools", ["read", "search", "grep", "bash"]),
                temperature=meta.get("temperature", 0.2),
            )
    except Exception as e:
        logger.log_warn("sub_agent", "load_custom", str(e))
    return None


sub_agent_registry: dict[str, SubAgent] = {}


def get_or_create_sub_agent(name: str) -> SubAgent | None:
    if name in sub_agent_registry:
        return sub_agent_registry[name]
    agent = get_sub_agent(name)
    if agent:
        sub_agent_registry[name] = agent
    return agent


def route_to_sub_agent(task: str, context: dict[str, Any] | None = None) -> str:
    task_lower = task.lower()
    if any(w in task_lower for w in ["verify", "validate", "test", "check quality", "lint"]):
        return "verifier"
    if any(w in task_lower for w in ["explore", "find", "search", "where is", "architecture"]):
        return "explorer"
    if any(w in task_lower for w in ["review", "audit", "security check"]):
        return "code_reviewer"
    if any(w in task_lower for w in ["plan", "design", "architecture", "how to", "approach"]):
        return "planner"
    if any(w in task_lower for w in ["error", "exception", "debug", "fix", "crash", "traceback"]):
        return "debugger"
    return "planner"
