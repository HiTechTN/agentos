"""Verify Mode — automatic code validation after execution."""

from app.agents.sub_agent import BUILTIN_SUB_AGENTS, SubAgent
from app.utils.logging import get_logger

logger = get_logger("verifier")


class VerificationResult:
    def __init__(self):
        self.passed: bool = False
        self.issues: list[dict] = []
        self.coverage_estimate: str = ""
        self.summary: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "issues": self.issues,
            "coverage_estimate": self.coverage_estimate,
            "summary": self.summary,
        }


class Verifier:
    def __init__(self):
        self.sub_agent = SubAgent(BUILTIN_SUB_AGENTS["verifier"])
        self.logger = get_logger("verifier")

    async def verify(
        self,
        task: str,
        code_changes: list[dict] | None = None,
        test_results: str = "",
        lint_output: str = "",
    ) -> VerificationResult:
        self.logger.log_action("verifier", "verify", "started", details={"task": task[:100]})
        result = VerificationResult()

        context = {
            "task": task,
            "code_changes": code_changes or [],
            "test_results": test_results,
            "lint_output": lint_output,
        }

        raw = await self.sub_agent.run("Verify the following changes:\n" + str(context))
        result.passed = raw.get("passed", False)
        result.issues = raw.get("issues", [])
        result.coverage_estimate = raw.get("coverage_estimate", "")
        result.summary = raw.get("summary", "")
        self.logger.log_action("verifier", "verify", "completed", details={"passed": result.passed})
        return result


verifier_instance: Verifier | None = None


def get_verifier() -> Verifier:
    global verifier_instance
    if verifier_instance is None:
        verifier_instance = Verifier()
    return verifier_instance
