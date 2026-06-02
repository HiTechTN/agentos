"""Tests for TreeOfThoughts — reasoning engine with MCTS scoring."""

from __future__ import annotations

import math

import pytest

from app.reasoning.tot_engine import ThoughtNode, TotResult, TreeOfThoughts


class TestThoughtNode:
    def test_thought_node_creation(self) -> None:
        node = ThoughtNode(
            thought="test thought",
            depth=2,
            is_terminal=True,
        )
        assert node.thought == "test thought"
        assert node.depth == 2
        assert node.is_terminal
        assert node.id is not None
        assert node.parent is None
        assert node.children == []
        assert node.score == 0.0
        assert node.visits == 0

    def test_thought_node_unique_ids(self) -> None:
        node1 = ThoughtNode()
        node2 = ThoughtNode()
        assert node1.id != node2.id

    def test_thought_node_parent_child_relation(self) -> None:
        parent = ThoughtNode(thought="parent")
        child = ThoughtNode(thought="child", parent=parent, depth=1)
        parent.children.append(child)
        assert child.parent is parent
        assert child in parent.children
        assert child.depth == 1


class TestEvaluateThought:
    def test_evaluate_thought_relevant(self) -> None:
        tot = TreeOfThoughts()
        score = tot._evaluate_thought("design architecture database", "Design the architecture")
        assert score > 0.0
        assert score <= 1.0

    def test_evaluate_thought_irrelevant(self) -> None:
        tot = TreeOfThoughts()
        score = tot._evaluate_thought("python programming", "blue ocean strategy")
        assert score == 0.0

    def test_evaluate_thought_empty_problem(self) -> None:
        tot = TreeOfThoughts()
        score = tot._evaluate_thought("", "anything")
        assert score == 0.5

    def test_evaluate_thought_exact_match(self) -> None:
        tot = TreeOfThoughts()
        score = tot._evaluate_thought("implement core logic", "implement core logic")
        assert score == 1.0


class TestGenerateThoughts:
    def test_generate_thoughts_depth_zero(self) -> None:
        tot = TreeOfThoughts(max_branches=2)
        thoughts = tot._generate_thoughts("problem", [], 0)
        assert len(thoughts) == 2
        assert "Understand the problem requirements" in thoughts
        assert "Identify key constraints" in thoughts

    def test_generate_thoughts_depth_one(self) -> None:
        tot = TreeOfThoughts(max_branches=3)
        thoughts = tot._generate_thoughts("problem", ["root"], 1)
        assert len(thoughts) == 3
        assert "Design the architecture" in thoughts

    def test_generate_thoughts_depth_two(self) -> None:
        tot = TreeOfThoughts(max_branches=1)
        thoughts = tot._generate_thoughts("problem", ["root", "mid"], 2)
        assert len(thoughts) == 1
        assert "Implement the core logic" in thoughts

    def test_generate_thoughts_unknown_depth(self) -> None:
        tot = TreeOfThoughts()
        thoughts = tot._generate_thoughts("problem", [], 99)
        assert thoughts == []


class TestMaxBranchesEnforced:
    def test_max_branches_enforced(self) -> None:
        tot = TreeOfThoughts(max_branches=1, max_depth=4)
        root = ThoughtNode(thought="root", depth=0)
        tot._expand("test problem", root)
        assert len(root.children) <= 1
        if root.children:
            tot._expand("test problem", root.children[0])
            assert len(root.children[0].children) <= 1


class TestUCB1:
    def test_exploration_weight_affects_ucb1(self) -> None:
        tot_low = TreeOfThoughts(exploration_weight=0.0)
        tot_high = TreeOfThoughts(exploration_weight=5.0)
        parent = ThoughtNode(thought="parent", visits=10)
        child = ThoughtNode(
            thought="child",
            parent=parent,
            visits=2,
            score=3.0,
        )
        low_score = tot_low._ucb1(child)
        high_score = tot_high._ucb1(child)
        assert low_score < high_score

    def test_ucb1_unvisited_child(self) -> None:
        tot = TreeOfThoughts()
        parent = ThoughtNode(thought="parent", visits=10)
        child = ThoughtNode(thought="child", parent=parent, visits=0)
        assert tot._ucb1(child) == float("inf")

    def test_ucb1_no_parent(self) -> None:
        tot = TreeOfThoughts()
        node = ThoughtNode(thought="root", visits=5, score=2.0)
        assert tot._ucb1(node) == node.score

    def test_ucb1_formula(self) -> None:
        tot = TreeOfThoughts(exploration_weight=1.4)
        parent = ThoughtNode(thought="parent", visits=10)
        child = ThoughtNode(thought="child", parent=parent, visits=3, score=4.0)
        result = tot._ucb1(child)
        exploitation = 4.0 / (3 + 1)
        exploration = 1.4 * math.sqrt(math.log(10 + 1) / (3 + 1))
        assert result == pytest.approx(exploitation + exploration)


class TestMCTSSearch:
    @pytest.mark.asyncio
    async def test_solve_returns_tot_result(self) -> None:
        tot = TreeOfThoughts()
        result = await tot.solve("design a system")
        assert isinstance(result, TotResult)
        assert result.best_thought
        assert isinstance(result.best_score, float)
        assert result.total_nodes > 0
        assert result.max_depth >= 0
        assert result.branches_evaluated >= 0

    @pytest.mark.asyncio
    async def test_solve_uses_mcts(self) -> None:
        tot = TreeOfThoughts(max_branches=2, max_depth=3)
        result = await tot.solve("build a web app")
        assert len(result.best_path) > 1

    @pytest.mark.asyncio
    async def test_best_path_follows_highest_score(self) -> None:
        tot = TreeOfThoughts(max_branches=2, max_depth=4)
        result = await tot.solve("optimize algorithm")
        path = result.best_path
        assert len(path) >= 1
        for i in range(1, len(path)):
            assert path[i].depth == path[i - 1].depth + 1

    @pytest.mark.asyncio
    async def test_max_depth_enforced(self) -> None:
        tot = TreeOfThoughts(max_branches=2, max_depth=2)
        result = await tot.solve("simple test")
        assert result.max_depth <= 2
        for node in result.best_path:
            assert node.depth <= 2


class TestCountAndCollect:
    def test_count_nodes_single(self) -> None:
        tot = TreeOfThoughts()
        root = ThoughtNode(thought="root")
        assert tot._count_nodes(root) == 1

    def test_count_nodes_tree(self) -> None:
        tot = TreeOfThoughts()
        root = ThoughtNode(thought="root")
        c1 = ThoughtNode(thought="c1", parent=root, depth=1)
        c2 = ThoughtNode(thought="c2", parent=root, depth=1)
        root.children = [c1, c2]
        assert tot._count_nodes(root) == 3

    def test_collect_nodes_depth_first(self) -> None:
        tot = TreeOfThoughts()
        root = ThoughtNode(thought="root")
        c1 = ThoughtNode(thought="c1", parent=root, depth=1)
        root.children = [c1]
        nodes = tot._collect_nodes(root)
        assert len(nodes) == 2
        assert root in nodes
        assert c1 in nodes


class TestBestPath:
    def test_best_path_root_only(self) -> None:
        tot = TreeOfThoughts()
        root = ThoughtNode(thought="root")
        path = tot._best_path(root)
        assert path == [root]

    def test_best_path_follows_children(self) -> None:
        tot = TreeOfThoughts()
        root = ThoughtNode(thought="root", score=1.0)
        c1 = ThoughtNode(thought="c1", parent=root, depth=1, score=5.0)
        c2 = ThoughtNode(thought="c2", parent=root, depth=1, score=2.0)
        root.children = [c1, c2]
        path = tot._best_path(root)
        assert path == [root, c1]


class TestBestLeaf:
    def test_best_leaf_single(self) -> None:
        tot = TreeOfThoughts()
        root = ThoughtNode(thought="root", score=3.0)
        assert tot._best_leaf(root) is root

    def test_best_leaf_picks_highest_score(self) -> None:
        tot = TreeOfThoughts()
        root = ThoughtNode(thought="root", score=1.0)
        c1 = ThoughtNode(thought="c1", parent=root, depth=1, score=5.0)
        c2 = ThoughtNode(thought="c2", parent=root, depth=1, score=10.0)
        c3 = ThoughtNode(thought="c3", parent=root, depth=1, score=2.0)
        root.children = [c1, c2, c3]
        assert tot._best_leaf(root) is c2


class TestPathThoughts:
    def test_path_thoughts_single(self) -> None:
        tot = TreeOfThoughts()
        root = ThoughtNode(thought="root")
        assert tot._path_thoughts(root) == ["root"]

    def test_path_thoughts_chain(self) -> None:
        tot = TreeOfThoughts()
        root = ThoughtNode(thought="root", depth=0)
        c1 = ThoughtNode(thought="middle", parent=root, depth=1)
        c2 = ThoughtNode(thought="leaf", parent=c1, depth=2)
        assert tot._path_thoughts(c2) == ["root", "middle", "leaf"]


class TestBackpropagate:
    def test_backpropagate_updates_all_ancestors(self) -> None:
        tot = TreeOfThoughts()
        root = ThoughtNode(thought="root", visits=0, score=0.0)
        c1 = ThoughtNode(thought="c1", parent=root, depth=1, visits=0, score=0.0)
        c2 = ThoughtNode(thought="c2", parent=c1, depth=2, visits=0, score=0.0)
        tot._backpropagate(c2, 7.0)
        assert c2.visits == 1
        assert c2.score == 7.0
        assert c1.visits == 1
        assert c1.score == 7.0
        assert root.visits == 1
        assert root.score == 7.0


class TestSimulate:
    def test_simulate_leaf_node(self) -> None:
        tot = TreeOfThoughts()
        node = ThoughtNode(thought="test")
        score = tot._simulate(node)
        assert 0.0 <= score <= 1.0

    def test_simulate_parent_averages_children(self) -> None:
        tot = TreeOfThoughts()
        parent = ThoughtNode(thought="parent")
        c1 = ThoughtNode(thought="implement core logic", parent=parent, depth=1)
        c2 = ThoughtNode(thought="implement core logic", parent=parent, depth=1)
        parent.children = [c1, c2]
        score = tot._simulate(parent)
        assert score == pytest.approx(c1.score)


class TestSelect:
    def test_select_leaf_node(self) -> None:
        tot = TreeOfThoughts()
        node = ThoughtNode(thought="root")
        assert tot._select(node) is node

    def test_select_follows_highest_ucb1(self) -> None:
        tot = TreeOfThoughts(exploration_weight=0.0)
        root = ThoughtNode(thought="root", visits=3)
        c1 = ThoughtNode(thought="c1", parent=root, depth=1, visits=2, score=10.0)
        c2 = ThoughtNode(thought="c2", parent=root, depth=1, visits=1, score=1.0)
        root.children = [c1, c2]
        assert tot._select(root) is c1


class TestExplorationWeightEffect:
    def test_exploration_weight_affects_scores(self) -> None:
        tot_default = TreeOfThoughts(exploration_weight=1.4)
        tot_zero = TreeOfThoughts(exploration_weight=0.0)
        child = ThoughtNode(
            thought="child",
            parent=ThoughtNode(thought="parent", visits=10),
            visits=2,
            score=3.0,
        )
        child.parent.children = [child]
        assert tot_default._ucb1(child) != tot_zero._ucb1(child)
