from typing import Any

# ruff: noqa: E402
"""Tests for AgentOS v4: sub-agent system, Plan/Code/Verify, Kanban, Pulse, git worktree, MCP."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.rules import RuleSystem
from app.agents.sub_agent import (
    BUILTIN_SUB_AGENTS,
    SubAgent,
    SubAgentConfig,
    get_sub_agent,
    route_to_sub_agent,
)
from app.kanban import COLUMNS, KanbanBoard, KanbanCard
from app.mcp.server import MCPRegistry
from app.pulse import PulseEngine, PulseSnapshot

# ── Sub-Agent System ───────────────────────────────────────────────────────────


class TestSubAgent:
    @pytest.mark.asyncio
    async def test_builtin_agents_defined(self) -> None:
        assert "planner" in BUILTIN_SUB_AGENTS
        assert "verifier" in BUILTIN_SUB_AGENTS
        assert "explorer" in BUILTIN_SUB_AGENTS
        assert "code_reviewer" in BUILTIN_SUB_AGENTS

    @pytest.mark.asyncio
    async def test_get_sub_agent(self) -> None:
        agent = get_sub_agent("verifier")
        assert agent is not None
        assert agent.config.name == "Verifier"

    @pytest.mark.asyncio
    async def test_get_nonexistent_sub_agent(self) -> None:
        agent = get_sub_agent("nonexistent_agent_xyz")
        assert agent is None

    @pytest.mark.asyncio
    async def test_sub_agent_run_with_mock(self) -> None:
        config = SubAgentConfig(name="TestAgent", system_prompt="You are a test agent.")
        agent = SubAgent(config)
        with patch.object(
            agent.llm, "chat", AsyncMock(return_value=MagicMock(content='{"result": "ok"}'))
        ):
            result = await agent.run("test task")
            assert result.get("result") == "ok"

    @pytest.mark.asyncio
    async def test_sub_agent_run_with_code_block(self) -> None:
        config = SubAgentConfig(name="TestAgent", system_prompt="test")
        agent = SubAgent(config)
        with patch.object(
            agent.llm,
            "chat",
            AsyncMock(return_value=MagicMock(content='```json\n{"key": "value"}\n```')),
        ):
            result = await agent.run("test")
            assert result.get("key") == "value"

    @pytest.mark.asyncio
    async def test_sub_agent_fallback_on_bad_json(self) -> None:
        config = SubAgentConfig(name="TestAgent", system_prompt="test")
        agent = SubAgent(config)
        with patch.object(
            agent.llm, "chat", AsyncMock(return_value=MagicMock(content="not json at all"))
        ):
            result = await agent.run("test")
            assert result.get("parsed") is False
            assert "raw_response" in result

    def test_route_to_sub_agent(self) -> None:
        assert route_to_sub_agent("verify this code") == "verifier"
        assert route_to_sub_agent("find where auth is") == "explorer"
        assert route_to_sub_agent("review security") == "code_reviewer"
        assert route_to_sub_agent("plan the approach") == "planner"
        assert route_to_sub_agent("debug the exception") == "debugger"
        assert route_to_sub_agent("something completely random") == "planner"

    def test_custom_sub_agent_config(self) -> None:
        config = SubAgentConfig(
            name="Custom",
            system_prompt="Custom test",
            model="test-model",
            tools=["read", "bash"],
            temperature=0.5,
            max_tokens=2048,
            auto_route=False,
        )
        assert config.name == "Custom"
        assert config.model == "test-model"
        assert config.temperature == 0.5
        assert config.max_tokens == 2048
        assert config.auto_route is False


# ── Rules System ───────────────────────────────────────────────────────────────


class TestRulesSystem:
    def test_rule_system_initialization(self, tmp_path: Any) -> None:
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("## Coding Standards\n- Use Python 3.13+")
        rules = RuleSystem(str(tmp_path))
        rules.load_all()
        assert len(rules._rules["project"]) > 0

    def test_get_project_rules(self, tmp_path: Any) -> None:
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("## Rules\n- Test thoroughly")
        rules = RuleSystem(str(tmp_path))
        rules.load_all()
        assert "Test thoroughly" in rules.get_project_rules()

    def test_get_all_rules_empty(self) -> None:
        rules = RuleSystem("/nonexistent")
        rules.load_all()
        assert rules.get_all_rules() == ""

    def test_create_default_agents_md(self, tmp_path: Any) -> None:
        rules = RuleSystem(str(tmp_path))
        rules.create_default_agents_md(str(tmp_path / "AGENTS.md"))
        assert (tmp_path / "AGENTS.md").exists()
        content = (tmp_path / "AGENTS.md").read_text()
        assert "AGENTS.md" in content


# ── Kanban Board ───────────────────────────────────────────────────────────────


class TestKanban:
    def test_add_card(self) -> None:
        board = KanbanBoard("test")
        card = board.add_card("Test Card", "Description", "todo", "task-1", "dev")
        assert card.id is not None
        assert card.title == "Test Card"
        assert card.column == "todo"

    def test_get_column(self) -> None:
        board = KanbanBoard("test")
        board.add_card("Card 1", column="todo")
        board.add_card("Card 2", column="todo")
        board.add_card("Card 3", column="done")
        assert len(board.get_column("todo")) == 2
        assert len(board.get_column("done")) == 1

    def test_move_card(self) -> None:
        board = KanbanBoard("test")
        card = board.add_card("Move me", column="todo")
        assert board.move_card(card.id, "in_progress") is True
        assert board.cards[card.id].column == "in_progress"
        assert board.move_card("nonexistent", "done") is False

    def test_delete_card(self) -> None:
        board = KanbanBoard("test")
        card = board.add_card("Delete me")
        assert board.delete_card(card.id) is True
        assert board.delete_card("nonexistent") is False

    def test_update_card(self) -> None:
        board = KanbanBoard("test")
        card = board.add_card("Update me")
        assert board.update_card(card.id, title="Updated", assignee="bot") is True
        assert board.cards[card.id].title == "Updated"
        assert board.cards[card.id].assignee == "bot"
        assert board.update_card("nonexistent", title="fail") is False

    def test_get_all(self) -> None:
        board = KanbanBoard("test")
        board.add_card("A", column="todo")
        board.add_card("B", column="done")
        all_cols = board.get_all()
        assert "todo" in all_cols
        assert "done" in all_cols
        assert len(all_cols["todo"]) == 1
        assert len(all_cols["done"]) == 1

    def test_columns_order(self) -> None:
        assert COLUMNS == ["backlog", "todo", "in_progress", "to_review", "done", "archived"]

    def test_invalid_column_fallback(self) -> None:
        card = KanbanCard("Test", column="invalid")
        assert card.column == "backlog"


# ── Pulse Dashboard ────────────────────────────────────────────────────────────


class TestPulse:
    @pytest.mark.asyncio
    async def test_snapshot_creation(self) -> None:
        pulse = PulseEngine()
        snap = await pulse.snapshot(
            {"todo": [{"id": "1"}], "in_progress": [{"id": "2"}], "done": [{"id": "3"}]},
            {"dev": "running", "content": "idle"},
        )
        assert snap.active_agents == 1
        assert snap.tasks_completed == 1
        assert snap.tasks_in_progress == 1

    @pytest.mark.asyncio
    async def test_timeline(self) -> None:
        pulse = PulseEngine()
        await pulse.snapshot({"todo": []}, {"dev": "idle"})
        await pulse.snapshot({"todo": []}, {"dev": "idle"})
        timeline = pulse.get_timeline(10)
        assert len(timeline) == 2

    def test_snapshot_to_dict(self) -> None:
        snap = PulseSnapshot()
        snap.add_metric("test_metric", 42.0, "ms")
        snap.active_agents = 3
        d = snap.to_dict()
        assert d["active_agents"] == 3
        assert len(d["metrics"]) == 1
        assert d["metrics"][0]["name"] == "test_metric"
        assert d["metrics"][0]["value"] == 42.0


# ── MCP Integration ────────────────────────────────────────────────────────────


class TestMCP:
    @pytest.mark.asyncio
    async def test_register_server(self) -> None:
        registry = MCPRegistry()
        registry.register("test-server", "http://localhost:9999")
        assert "test-server" in registry.servers

    @pytest.mark.asyncio
    async def test_list_servers(self) -> None:
        registry = MCPRegistry()
        registry.register("s1", "http://a")
        registry.register("s2", "http://b")
        servers = registry.list_servers()
        assert len(servers) == 2

    @pytest.mark.asyncio
    async def test_unregister_server(self) -> None:
        registry = MCPRegistry()
        registry.register("to-remove", "http://x")
        registry.unregister("to-remove")
        assert "to-remove" not in registry.servers

    @pytest.mark.asyncio
    async def test_call_tool_no_server(self) -> None:
        registry = MCPRegistry()
        result = await registry.call_tool("nonexistent", "test")
        assert "error" in result
