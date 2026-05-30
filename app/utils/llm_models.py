"""LLM model definitions, catalogues, and work-type detection for AgentOS."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class WorkType(str, Enum):  # noqa: UP042
    """Categories of LLM work — determines which free model is selected."""

    CODE_GEN = "code_gen"
    CODE_AGENT = "code_agent"
    REASONING = "reasoning"
    CONTENT = "content"
    FAST = "fast"
    MULTIMODAL = "multimodal"
    DEBUG = "debug"
    GENERAL = "general"


@dataclass
class FreeModel:
    """A single free OpenRouter model with its capabilities."""

    id: str
    name: str
    context_window: int
    supports_tools: bool = False
    supports_vision: bool = False
    supports_reasoning: bool = False
    req_per_min: int = 20
    req_per_day: int = 200


FREE_MODELS: dict[WorkType, list[FreeModel]] = {
    WorkType.CODE_GEN: [
        FreeModel(
            id="qwen/qwen3-coder:free",
            name="Qwen3 Coder",
            context_window=1_000_000,
            supports_tools=True,
        ),
        FreeModel(
            id="deepseek/deepseek-v4-flash:free",
            name="DeepSeek V4 Flash",
            context_window=1_000_000,
            supports_tools=True,
            supports_reasoning=True,
        ),
        FreeModel(
            id="openai/gpt-oss-120b:free",
            name="GPT-OSS 120B",
            context_window=128_000,
            supports_tools=True,
        ),
    ],
    WorkType.CODE_AGENT: [
        FreeModel(
            id="poolside/laguna-m1:free",
            name="Laguna M.1",
            context_window=128_000,
            supports_tools=True,
        ),
        FreeModel(
            id="qwen/qwen3-coder:free",
            name="Qwen3 Coder",
            context_window=1_000_000,
            supports_tools=True,
        ),
        FreeModel(
            id="openai/gpt-oss-120b:free",
            name="GPT-OSS 120B",
            context_window=128_000,
            supports_tools=True,
        ),
    ],
    WorkType.REASONING: [
        FreeModel(
            id="deepseek/deepseek-r1:free",
            name="DeepSeek R1",
            context_window=128_000,
            supports_reasoning=True,
        ),
        FreeModel(
            id="google/gemini-2.0-pro:free",
            name="Gemini 2.0 Pro",
            context_window=2_000_000,
            supports_tools=True,
            supports_vision=True,
        ),
        FreeModel(
            id="nvidia/llama-3.1-nemotron-70b-instruct:free",
            name="Nemotron 70B",
            context_window=128_000,
        ),
    ],
    WorkType.CONTENT: [
        FreeModel(
            id="google/gemini-2.0-flash:free",
            name="Gemini 2.0 Flash",
            context_window=1_048_576,
            supports_tools=True,
            supports_vision=True,
        ),
        FreeModel(
            id="meta-llama/llama-3.3-70b-instruct:free",
            name="Llama 3.3 70B",
            context_window=128_000,
            supports_tools=True,
        ),
        FreeModel(
            id="mistralai/mistral-small-3:free",
            name="Mistral Small 3",
            context_window=32_000,
            supports_tools=True,
        ),
    ],
    WorkType.FAST: [
        FreeModel(
            id="mistralai/mistral-small-3:free",
            name="Mistral Small 3",
            context_window=32_000,
            supports_tools=True,
        ),
        FreeModel(
            id="qwen/qwen-2.5-7b-instruct:free",
            name="Qwen 2.5 7B",
            context_window=128_000,
        ),
        FreeModel(
            id="google/gemini-2.0-flash:free",
            name="Gemini 2.0 Flash",
            context_window=1_048_576,
            supports_tools=True,
        ),
    ],
    WorkType.MULTIMODAL: [
        FreeModel(
            id="qwen/qwen-2.5-vl-72b-instruct:free",
            name="Qwen 2.5 VL 72B",
            context_window=128_000,
            supports_vision=True,
        ),
        FreeModel(
            id="google/gemini-2.0-flash:free",
            name="Gemini 2.0 Flash",
            context_window=1_048_576,
            supports_tools=True,
            supports_vision=True,
        ),
        FreeModel(
            id="google/gemini-2.0-pro:free",
            name="Gemini 2.0 Pro",
            context_window=2_000_000,
            supports_vision=True,
        ),
    ],
    WorkType.DEBUG: [
        FreeModel(
            id="deepseek/deepseek-v4-flash:free",
            name="DeepSeek V4 Flash",
            context_window=1_000_000,
            supports_tools=True,
            supports_reasoning=True,
        ),
        FreeModel(
            id="qwen/qwen3-coder:free",
            name="Qwen3 Coder",
            context_window=1_000_000,
            supports_tools=True,
        ),
        FreeModel(
            id="deepseek/deepseek-r1:free",
            name="DeepSeek R1",
            context_window=128_000,
            supports_reasoning=True,
        ),
    ],
    WorkType.GENERAL: [
        FreeModel(
            id="nvidia/llama-3.1-nemotron-70b-instruct:free",
            name="Nemotron 70B",
            context_window=128_000,
        ),
        FreeModel(
            id="meta-llama/llama-3.3-70b-instruct:free",
            name="Llama 3.3 70B",
            context_window=128_000,
            supports_tools=True,
        ),
        FreeModel(
            id="openrouter/free",
            name="OpenRouter Auto",
            context_window=200_000,
            supports_tools=True,
        ),
    ],
}

_WORK_TYPE_KEYWORDS: dict[WorkType, list[str]] = {
    WorkType.CODE_GEN: [
        "scaffold",
        "implement",
        "refactor",
        "generate code",
        "write function",
        "create class",
        "write tests",
        "fix bug",
        "code generation",
    ],
    WorkType.CODE_AGENT: [
        "agent",
        "agentic",
        "multi-step",
        "tool call",
        "workflow",
        "pipeline",
        "automate",
    ],
    WorkType.REASONING: [
        "plan",
        "architecture",
        "design",
        "analyze",
        "reason",
        "compare",
        "evaluate",
        "strategy",
        "structured plan",
        "phases",
        "dependencies",
    ],
    WorkType.CONTENT: [
        "seo",
        "copy",
        "blog",
        "article",
        "social media",
        "marketing",
        "email campaign",
        "content",
        "write",
    ],
    WorkType.FAST: [
        "classify",
        "extract",
        "summarize",
        "translate",
        "quick",
        "fast",
        "short",
    ],
    WorkType.MULTIMODAL: [
        "image",
        "vision",
        "screenshot",
        "photo",
        "visual",
        "describe image",
        "analyze image",
    ],
    WorkType.DEBUG: [
        "debug",
        "error",
        "exception",
        "traceback",
        "crash",
        "fix error",
        "stack trace",
        "why is",
        "not working",
    ],
}


def detect_work_type(prompt: str, agent_name: str = "") -> WorkType:
    """Infer the WorkType from prompt content and agent name."""
    text = (prompt + " " + agent_name).lower()

    agent_map: dict[str, WorkType] = {
        "devagent": WorkType.CODE_AGENT,
        "contentagent": WorkType.CONTENT,
        "marketingagent": WorkType.CONTENT,
        "commerceagent": WorkType.REASONING,
        "@planner": WorkType.REASONING,
        "@verifier": WorkType.CODE_GEN,
        "@explorer": WorkType.FAST,
        "@codereviewer": WorkType.CODE_GEN,
        "@debugger": WorkType.DEBUG,
    }
    for agent_key, work_type in agent_map.items():
        if agent_key in text:
            return work_type
    scores: dict[WorkType, int] = {wt: 0 for wt in WorkType}
    for work_type, keywords in _WORK_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[work_type] += 1
    best = max(scores, key=lambda k: scores[k])
    if scores[best] > 0:
        return best
    return WorkType.GENERAL
