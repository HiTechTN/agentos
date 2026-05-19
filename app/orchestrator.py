import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Literal

import yaml

from app.agents import DevAgent, ContentAgent, MarketingAgent, CommerceAgent
from app.memory.session import SessionManager, get_session_manager
from app.memory.vector_store import VectorStore, get_vector_store
from app.utils.logging import get_logger
from app.utils.hitl_gateway import HITLPendingError, get_hitl_gateway


class AgentOSState(TypedDict):
    project_id: str
    session_id: str
    trace_id: str
    prompt: str
    tasks: list[dict]
    current_task_index: int
    agent_sequence: list[str]
    results: dict[str, Any]
    errors: list[dict]
    pending_hitl: list[str]
    status: str
    circuit_breaker: dict[str, int]
    start_time: float


class CircuitBreakerOpen(Exception):
    pass


MAX_RETRIES = 3
CIRCUIT_BREAKER_THRESHOLD = 3
TASK_PRIORITY_DEFAULT = 0


def load_policies() -> dict:
    import os
    path = os.path.join(os.path.dirname(__file__), "config", "policies.yaml")
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


class AgentOSOrchestrator:
    def __init__(self):
        self.logger = get_logger("orchestrator")
        self.session_manager = get_session_manager()
        self.vector_store = get_vector_store()
        self.hitl_gateway = get_hitl_gateway()
        self.policies = load_policies()

        self.agents = {
            "dev": DevAgent(),
            "content": ContentAgent(),
            "marketing": MarketingAgent(),
            "commerce": CommerceAgent(),
        }

        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(AgentOSState)

        workflow.add_node("analyze_prompt", self._analyze_prompt)
        workflow.add_node("route_tasks", self._route_tasks)
        workflow.add_node("execute_dev", self._execute_dev)
        workflow.add_node("execute_content", self._execute_content)
        workflow.add_node("execute_marketing", self._execute_marketing)
        workflow.add_node("execute_commerce", self._execute_commerce)
        workflow.add_node("check_results", self._check_results)
        workflow.add_node("handle_error", self._handle_error)
        workflow.add_node("finalize", self._finalize)

        workflow.set_entry_point("analyze_prompt")

        workflow.add_conditional_edges(
            "analyze_prompt",
            self._decide_routing,
            {"route": "route_tasks", "error": "handle_error"},
        )

        workflow.add_conditional_edges(
            "route_tasks",
            self._decide_execution_order,
            {
                "dev": "execute_dev",
                "content": "execute_content",
                "marketing": "execute_marketing",
                "commerce": "execute_commerce",
                "parallel_dev_content": "execute_dev",
                "finalize": "check_results",
                "error": "handle_error",
            },
        )

        workflow.add_edge("execute_dev", "check_results")
        workflow.add_edge("execute_content", "check_results")
        workflow.add_edge("execute_marketing", "check_results")
        workflow.add_edge("execute_commerce", "check_results")

        workflow.add_conditional_edges(
            "check_results",
            self._decide_next,
            {
                "continue": "route_tasks",
                "finalize": "finalize",
                "error": "handle_error",
            },
        )

        workflow.add_conditional_edges(
            "handle_error",
            self._decide_retry,
            {
                "retry": "route_tasks",
                "circuit_open": "finalize",
                "fail": "finalize",
                "end": END,
            },
        )

        workflow.add_edge("finalize", END)

        return workflow.compile()

    async def run(self, prompt: str, project_id: str = "") -> dict:
        trace_id = str(uuid.uuid4())
        session_id = await self.session_manager.create(project_id or "default", trace_id)
        project_id = project_id or "default"

        initial_state: AgentOSState = {
            "project_id": project_id,
            "session_id": session_id,
            "trace_id": trace_id,
            "prompt": prompt,
            "tasks": [],
            "current_task_index": 0,
            "agent_sequence": [],
            "results": {},
            "errors": [],
            "pending_hitl": [],
            "status": "running",
            "circuit_breaker": {k: 0 for k in self.agents},
            "start_time": time.time(),
        }

        self.logger.log_action(
            agent_id="orchestrator",
            action="workflow_start",
            status="started",
            trace_id=trace_id,
            project_id=project_id,
            details={"prompt": prompt[:200]},
        )

        try:
            result = await self.graph.ainvoke(initial_state)
            return result
        except Exception as e:
            self.logger.log_error(
                agent_id="orchestrator",
                action="workflow",
                error=str(e),
                trace_id=trace_id,
                project_id=project_id,
            )
            return {
                "status": "failed",
                "error": {"code": "ORCHESTRATION_FAILED", "message": str(e)},
                "session_id": session_id,
                "trace_id": trace_id,
            }

    async def _analyze_prompt(self, state: AgentOSState) -> dict:
        try:
            tasks = await self._decompose_prompt(state["prompt"])
            return {"tasks": tasks, "status": "analyzed"}
        except Exception as e:
            return {"errors": [{"code": "ANALYSIS_FAILED", "message": str(e)}], "status": "error"}

    async def _decompose_prompt(self, prompt: str) -> list[dict]:
        from app.utils.api_clients import LLMClient
        llm = LLMClient()
        response = await llm.chat(
            model="openai/gpt-4o-2024-11-20",
            messages=[
                {"role": "system", "content": """Decompose the user prompt into AgentOS tasks.
Available agents: dev (code/scaffold/deploy), content (write/image/publish),
marketing (segment/email/ads/report), commerce (catalog/pricing/checkout/inventory/faq).

Return ONLY a JSON array of objects: [{"agent": "dev", "action": "scaffold", "params": {}, "priority": 0}]"""},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        try:
            cleaned = response.content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            tasks = json.loads(cleaned)
            if isinstance(tasks, dict):
                tasks = [tasks]
            for t in tasks:
                t.setdefault("priority", TASK_PRIORITY_DEFAULT)
            return tasks
        except (json.JSONDecodeError, AttributeError) as e:
            self.logger.log_warn("orchestrator", "decompose", f"Failed to parse tasks: {e}")
            return [{"agent": "dev", "action": "analyze", "params": {"prompt": prompt}, "priority": 0}]

    def _decide_routing(self, state: AgentOSState) -> str:
        if state.get("errors"):
            return "error"
        return "route"

    def _decide_execution_order(self, state: AgentOSState) -> str:
        tasks = state.get("tasks", [])
        if not tasks or state["current_task_index"] >= len(tasks):
            return "finalize"

        current = tasks[state["current_task_index"]]
        agent = current.get("agent", "")

        state["agent_sequence"] = [t["agent"] for t in tasks]

        next_tasks = tasks[state["current_task_index"]:]
        agents_in_order = [t["agent"] for t in next_tasks]

        if all(a == agents_in_order[0] for a in agents_in_order):
            return agents_in_order[0]

        if agent in self.agents:
            return agent

        return "finalize"

    async def _execute_agent(self, state: AgentOSState, agent_name: str) -> dict:
        agent = self.agents.get(agent_name)
        if not agent:
            return {"errors": [{"code": "UNKNOWN_AGENT", "message": f"Unknown agent: {agent_name}"}]}

        cb_key = agent_name
        if state["circuit_breaker"].get(cb_key, 0) >= CIRCUIT_BREAKER_THRESHOLD:
            self.logger.log_warn("orchestrator", "circuit_open", f"Circuit breaker open for {agent_name}")
            return {"errors": [{"code": "CIRCUIT_OPEN", "message": f"Circuit breaker open for {agent_name}"}]}

        tasks = state["tasks"]
        idx = state["current_task_index"]
        current_tasks = []

        if state.get("agent_sequence", []) and agent_name == state["agent_sequence"][0]:
            current_tasks = [t for t in tasks if t["agent"] == agent_name]
        elif idx < len(tasks):
            current_tasks = [tasks[idx]]

        if not current_tasks:
            return {"current_task_index": idx + 1}

        for task in current_tasks:
            for attempt in range(MAX_RETRIES):
                try:
                    result = await agent.execute(
                        task=task,
                        session_id=state["session_id"],
                        trace_id=state["trace_id"],
                    )
                    if result.get("success"):
                        state["circuit_breaker"][cb_key] = 0
                        results_key = f"{agent_name}_{task['action']}"
                        new_results = state.get("results", {})
                        new_results[results_key] = result
                        return {
                            "results": new_results,
                            "current_task_index": idx + 1,
                            "circuit_breaker": state["circuit_breaker"],
                        }
                    else:
                        state["circuit_breaker"][cb_key] = state["circuit_breaker"].get(cb_key, 0) + 1
                        if attempt < MAX_RETRIES - 1:
                            continue
                        return {
                            "errors": state["errors"] + [result.get("error", {"code": "AGENT_FAILED"})],
                            "circuit_breaker": state["circuit_breaker"],
                        }
                except HITLPendingError as e:
                    return {
                        "pending_hitl": state.get("pending_hitl", []) + [e.approval_id],
                        "status": "waiting_hitl",
                    }
                except Exception as e:
                    state["circuit_breaker"][cb_key] = state["circuit_breaker"].get(cb_key, 0) + 1
                    if attempt < MAX_RETRIES - 1:
                        continue
                    return {"errors": state["errors"] + [{"code": "EXECUTION_ERROR", "message": str(e)}]}

        return {"current_task_index": idx + 1}

    async def _execute_dev(self, state: AgentOSState) -> dict:
        return await self._execute_agent(state, "dev")

    async def _execute_content(self, state: AgentOSState) -> dict:
        return await self._execute_agent(state, "content")

    async def _execute_marketing(self, state: AgentOSState) -> dict:
        return await self._execute_agent(state, "marketing")

    async def _execute_commerce(self, state: AgentOSState) -> dict:
        return await self._execute_agent(state, "commerce")

    async def _check_results(self, state: AgentOSState) -> dict:
        status = "continue"
        if state.get("pending_hitl"):
            return {"status": "waiting_hitl"}
        if state.get("errors"):
            status = "error"
        elif state["current_task_index"] >= len(state["tasks"]):
            status = "finalize"
        return {"status": status}

    def _decide_next(self, state: AgentOSState) -> str:
        s = state.get("status", "")
        if s == "waiting_hitl":
            return "finalize"
        if s == "error":
            return "error"
        if state.get("pending_hitl"):
            return "finalize"
        if state["current_task_index"] >= len(state["tasks"]):
            return "finalize"
        return "continue"

    def _decide_retry(self, state: AgentOSState) -> str:
        for agent_name, fail_count in state["circuit_breaker"].items():
            if fail_count >= CIRCUIT_BREAKER_THRESHOLD:
                self.logger.log_error("orchestrator", "circuit_breaker", f"Circuit opened for {agent_name} after {fail_count} failures")
                return "circuit_open"
        return "fail"

    async def _handle_error(self, state: AgentOSState) -> dict:
        status = "failed"
        for name, count in state["circuit_breaker"].items():
            if count >= CIRCUIT_BREAKER_THRESHOLD:
                status = "circuit_open"
                break
        return {"status": status}

    async def _finalize(self, state: AgentOSState) -> dict:
        elapsed = time.time() - state["start_time"]
        status = "completed" if not state.get("errors") else "completed_with_errors"

        await self.session_manager.update(
            state["session_id"],
            context={"results": state.get("results", {}), "errors": state.get("errors", [])},
            status=status,
        )

        self.logger.log_action(
            agent_id="orchestrator",
            action="workflow_complete",
            status=status,
            trace_id=state["trace_id"],
            project_id=state["project_id"],
            details={"elapsed_seconds": round(elapsed, 2), "tasks": len(state["tasks"]), "errors": len(state.get("errors", []))},
        )

        return {
            "status": status,
            "elapsed_seconds": round(elapsed, 2),
        }

    async def route_tasks(self, state: AgentOSState) -> dict:
        return await self._route_tasks(state)

    async def _route_tasks(self, state: AgentOSState) -> dict:
        return {"status": "routed"}


_orchestrator: AgentOSOrchestrator | None = None


def get_orchestrator() -> AgentOSOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOSOrchestrator()
    return _orchestrator
