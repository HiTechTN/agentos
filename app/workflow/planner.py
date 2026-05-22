"""Plan Mode — structured plan output from user requirements."""

import json
from datetime import UTC, datetime

from app.agents.rules import get_rules
from app.agents.sub_agent import BUILTIN_SUB_AGENTS, SubAgent
from app.utils.api_clients import LLMClient
from app.utils.logging import get_logger

logger = get_logger("planner")


class PlanPhase:
    def __init__(self, name: str, description: str, order: int = 0):
        self.name = name
        self.description = description
        self.order = order
        self.tasks: list[PlanTask] = []

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "order": self.order,
            "tasks": [t.to_dict() for t in self.tasks],
        }


class PlanTask:
    def __init__(
        self,
        title: str,
        description: str = "",
        agent: str = "dev",
        dependencies: list[str] | None = None,
        estimated_minutes: int = 30,
    ):
        self.id = f"task_{datetime.now(UTC).timestamp()}"
        self.title = title
        self.description = description
        self.agent = agent
        self.dependencies = dependencies or []
        self.estimated_minutes = estimated_minutes

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "agent": self.agent,
            "dependencies": self.dependencies,
            "estimated_minutes": self.estimated_minutes,
        }


class Plan:
    def __init__(self, goal: str):
        self.goal = goal
        self.phases: list[PlanPhase] = []
        self.risks: list[str] = []
        self.stack: str = ""
        self.architecture_summary: str = ""
        self.created_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "phases": [p.to_dict() for p in self.phases],
            "risks": self.risks,
            "stack": self.stack,
            "architecture_summary": self.architecture_summary,
            "created_at": self.created_at,
        }


class Planner:
    def __init__(self):
        self.llm = LLMClient()
        self.logger = get_logger("planner")
        self.rules = get_rules()

    async def create_plan(self, goal: str, context: dict | None = None) -> Plan:
        self.logger.log_action("planner", "create_plan", "started", details={"goal": goal[:100]})
        plan = Plan(goal)

        sub_agent = SubAgent(BUILTIN_SUB_AGENTS["planner"])
        rules_text = self.rules.get_all_rules()

        full_context = {
            "goal": goal,
            "rules": rules_text,
            "project_context": context or {},
        }

        result = await sub_agent.run(json.dumps(full_context))

        if "phases" in result:
            for phase_data in result["phases"]:
                phase = PlanPhase(
                    name=phase_data.get("name", "Untitled"),
                    description=phase_data.get("description", ""),
                    order=phase_data.get("order", 0),
                )
                for task_data in phase_data.get("tasks", []):
                    task = PlanTask(
                        title=task_data.get("title", "Untitled"),
                        description=task_data.get("description", ""),
                        agent=task_data.get("agent", "dev"),
                        dependencies=task_data.get("dependencies", []),
                        estimated_minutes=task_data.get("estimated_minutes", 30),
                    )
                    phase.tasks.append(task)
                plan.phases.append(phase)

        plan.risks = result.get("risks", [])
        plan.stack = result.get("stack", "")
        plan.architecture_summary = result.get("architecture_summary", "")

        self.logger.log_action(
            "planner",
            "create_plan",
            "completed",
            details={"phases": len(plan.phases), "tasks": sum(len(p.tasks) for p in plan.phases)},
        )
        return plan


planner_instance: Planner | None = None


def get_planner() -> Planner:
    global planner_instance
    if planner_instance is None:
        planner_instance = Planner()
    return planner_instance
