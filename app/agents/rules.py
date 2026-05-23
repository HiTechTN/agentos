"""AGENTS.md rule system — project-level + global rules."""

import os
import re
from pathlib import Path
from typing import Any

from app.utils.logging import get_logger

logger = get_logger("rules")

DEFAULT_GLOBAL_RULES_PATH = os.path.expanduser("~/.agentos/VERDENT.md")
DEFAULT_PLAN_RULES_PATH = os.path.expanduser("~/.agentos/plan_rules.md")


class RuleSystem:
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self._rules: dict[str, list[str]] = {
            "global": [],
            "project": [],
            "plan": [],
        }
        self._parsed: dict[str, Any] = {}

    def load_all(self) -> None:
        self._load_global()
        self._load_project()
        self._load_plan()

    def _load_global(self) -> None:
        path = Path(DEFAULT_GLOBAL_RULES_PATH)
        if path.exists():
            self._rules["global"] = self._parse_file(path)

    def _load_project(self) -> None:
        candidates = [
            self.project_root / "AGENTS.md",
            self.project_root / "agents.md",
            self.project_root / ".agentos" / "AGENTS.md",
        ]
        for path in candidates:
            if path.exists():
                self._rules["project"] = self._parse_file(path)
                break

    def _load_plan(self) -> None:
        path = Path(DEFAULT_PLAN_RULES_PATH)
        if path.exists():
            self._rules["plan"] = self._parse_file(path)

    def _parse_file(self, path: Path) -> list[str]:
        try:
            content = path.read_text()
            sections = re.split(r"\n##+\s+", content)
            result = [s.strip() for s in sections if s.strip()]
            return result
        except Exception as e:
            logger.log_warn("rules", "parse", f"Failed to parse {path}: {e}")
            return []

    def get_project_rules(self) -> str:
        return "\n".join(self._rules["project"]) if self._rules["project"] else ""

    def get_global_rules(self) -> str:
        return "\n".join(self._rules["global"]) if self._rules["global"] else ""

    def get_plan_rules(self) -> str:
        return "\n".join(self._rules["plan"]) if self._rules["plan"] else ""

    def get_all_rules(self) -> str:
        parts = []
        if self._rules["project"]:
            parts.append("## Project Rules (AGENTS.md)\n" + self.get_project_rules())
        if self._rules["global"]:
            parts.append("## Global Rules\n" + self.get_global_rules())
        if self._rules["plan"]:
            parts.append("## Plan Rules\n" + self.get_plan_rules())
        return "\n\n".join(parts)

    def create_default_agents_md(self, path: str | None = None) -> None:
        target = Path(path or self.project_root / "AGENTS.md")
        if not target.exists():
            content = """# AGENTS.md — AgentOS Project Rules

## Coding Standards
- Use TypeScript for frontend code
- Use Python 3.13+ for backend code
- Follow the existing code style in the project
- Write tests for all new features

## Architecture
- Keep components small and focused
- Use dependency injection where appropriate
- Document public APIs

## Verification
- Run tests before marking tasks complete
- Check for type errors
- Ensure no security vulnerabilities

## Preferences
- Prefer async/await over callbacks
- Use composition over inheritance
- Keep functions under 50 lines
"""
            target.write_text(content)
            logger.log_action(
                "rules", "create_agents_md", "completed", details={"path": str(target)}
            )


_rules_system: RuleSystem | None = None


def get_rules(project_root: str = ".") -> RuleSystem:
    global _rules_system
    if _rules_system is None:
        _rules_system = RuleSystem(project_root)
        _rules_system.load_all()
    return _rules_system
