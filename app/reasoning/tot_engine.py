"""Tree of Thoughts reasoning engine with MCTS scoring for AgentOS."""

import math
import uuid
from dataclasses import dataclass, field


@dataclass
class ThoughtNode:
    """A single node in the Tree of Thoughts search tree.

    Attributes:
        id: Unique identifier for this node (uuid4 string).
        thought: The thought/idea content at this node.
        parent: The parent node, or None if this is the root.
        children: List of child ThoughtNode instances.
        score: MCTS UCB score for this node.
        visits: Number of times this node has been visited during search.
        depth: Depth of this node in the tree (root = 0).
        is_terminal: Whether this node represents a terminal state.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    thought: str = ""
    parent: "ThoughtNode | None" = None
    children: list["ThoughtNode"] = field(default_factory=list)
    score: float = 0.0
    visits: int = 0
    depth: int = 0
    is_terminal: bool = False


@dataclass
class TotResult:
    """Result of a Tree of Thoughts search.

    Attributes:
        best_path: Ordered list of ThoughtNode from root to best leaf.
        best_thought: The thought content at the best leaf node.
        best_score: The score of the best leaf node.
        total_nodes: Total number of nodes created during search.
        max_depth: Maximum depth reached in the tree.
        branches_evaluated: Number of branches evaluated during search.
    """

    best_path: list[ThoughtNode]
    best_thought: str
    best_score: float
    total_nodes: int
    max_depth: int
    branches_evaluated: int


class TreeOfThoughts:
    """Tree of Thoughts planner using Monte Carlo Tree Search.

    Generates a search tree of possible reasoning steps, evaluates each
    thought, and explores the most promising branches using UCB1 scoring.

    Attributes:
        max_branches: Maximum number of child thoughts per node.
        max_depth: Maximum depth of the search tree.
        exploration_weight: Exploration parameter C for UCB1 formula.
    """

    def __init__(
        self,
        max_branches: int = 2,
        max_depth: int = 3,
        exploration_weight: float = 1.4,
    ) -> None:
        """Initialize the Tree of Thoughts engine.

        Args:
            max_branches: Maximum number of child thoughts per node.
            max_depth: Maximum depth of the search tree.
            exploration_weight: Exploration parameter C for UCB1 formula.
        """
        self.max_branches = max_branches
        self.max_depth = max_depth
        self.exploration_weight = exploration_weight

    async def solve(self, problem: str) -> TotResult:
        """Solve a problem using Tree of Thoughts with MCTS.

        Builds a search tree by iteratively generating, evaluating, and
        backpropagating scores through the tree.

        Args:
            problem: The problem description to reason about.

        Returns:
            A TotResult containing the best reasoning path and metrics.
        """
        root = ThoughtNode(thought=problem, depth=0)
        best_node = self._mcts_search(problem, root)
        path = self._best_path(root)
        return TotResult(
            best_path=path,
            best_thought=path[-1].thought if path else problem,
            best_score=best_node.score if best_node else 0.0,
            total_nodes=self._count_nodes(root),
            max_depth=max(n.depth for n in self._collect_nodes(root)),
            branches_evaluated=sum(len(n.children) for n in self._collect_nodes(root)),
        )

    def _generate_thoughts(
        self,
        problem: str,
        current_path: list[str],
        depth: int,
    ) -> list[str]:
        """Generate possible next thoughts for a given depth.

        Produces deterministic candidate thoughts based on the current
        depth level, truncated to max_branches.

        Args:
            problem: The original problem description.
            current_path: The sequence of thoughts leading to this node.
            depth: Current depth in the search tree.

        Returns:
            A list of thought strings, up to max_branches in length.
        """
        _ = problem
        _ = current_path
        thoughts_by_depth: dict[int, list[str]] = {
            0: [
                "Understand the problem requirements",
                "Identify key constraints",
                "Outline the solution approach",
            ],
            1: [
                "Design the architecture",
                "Define data structures",
                "Plan the implementation",
            ],
            2: [
                "Implement the core logic",
                "Handle edge cases",
                "Optimize performance",
            ],
        }
        candidates = thoughts_by_depth.get(depth, [])
        return candidates[: self.max_branches]

    def _evaluate_thought(self, problem: str, thought: str) -> float:
        """Score a thought based on keyword relevance to the problem.

        Counts how many keywords from the problem appear in the thought
        string, normalized by the total number of keywords extracted.

        Args:
            problem: The original problem description.
            thought: The thought content to evaluate.

        Returns:
            A float score between 0.0 and 1.0.
        """
        keywords = set(problem.lower().split())
        thought_words = set(thought.lower().split())
        if not keywords:
            return 0.5
        matches = keywords & thought_words
        return len(matches) / len(keywords)

    def _mcts_search(
        self,
        problem: str,
        root: ThoughtNode,
    ) -> ThoughtNode:
        """Perform Monte Carlo Tree Search over the thought tree.

        Runs 10 iterations of the MCTS cycle: select, expand, simulate,
        and backpropagate.

        Args:
            problem: The original problem description.
            root: The root ThoughtNode to search from.

        Returns:
            The highest-scoring ThoughtNode found.
        """
        for _iteration in range(10):
            _ = _iteration
            leaf = self._select(root)
            if not leaf.is_terminal and leaf.depth < self.max_depth:
                self._expand(problem, leaf)
            self._simulate(leaf)
            self._backpropagate(leaf, leaf.score)
        return self._best_leaf(root)

    def _select(self, node: ThoughtNode) -> ThoughtNode:
        """Traverse from root to a leaf using UCB1 selection.

        At each step, picks the child with the highest UCB1 score until
        a node with no children (leaf) is reached.

        Args:
            node: The starting node (typically root).

        Returns:
            A leaf ThoughtNode.
        """
        while node.children:
            node = max(node.children, key=self._ucb1)
        return node

    def _expand(self, problem: str, node: ThoughtNode) -> None:
        """Generate and attach child thoughts to a node.

        Creates ThoughtNode children using _generate_thoughts based on
        the current path from root.

        Args:
            problem: The original problem description.
            node: The node to expand.
        """
        current_path = self._path_thoughts(node)
        thoughts = self._generate_thoughts(problem, current_path, node.depth)
        for thought_text in thoughts:
            child = ThoughtNode(
                thought=thought_text,
                parent=node,
                depth=node.depth + 1,
                is_terminal=(node.depth + 1 >= self.max_depth),
            )
            node.children.append(child)

    def _simulate(self, node: ThoughtNode) -> float:
        """Evaluate the score for a node and its children recursively.

        Propagates evaluation scores upward: a node's score is the
        average of its children's scores, or its direct evaluation if
        it has no children.

        Args:
            node: The node to simulate from.

        Returns:
            The computed score for this node.
        """
        if not node.children:
            node.score = self._evaluate_thought(node.thought, node.thought)
            return node.score
        total = 0.0
        for child in node.children:
            total += self._simulate(child)
        node.score = total / len(node.children)
        return node.score

    def _backpropagate(self, node: ThoughtNode, score: float) -> None:
        """Propagate evaluation results up the tree.

        Updates visits and accumulated score for each node along the
        path from the given node to the root.

        Args:
            node: The node to backpropagate from.
            score: The score to propagate upward.
        """
        current: ThoughtNode | None = node
        while current is not None:
            current.visits += 1
            current.score += score
            current = current.parent

    def _ucb1(self, node: ThoughtNode) -> float:
        """Compute the UCB1 score for a child node.

        UCB1 = child_score + C * sqrt(log(parent_visits) / (child_visits + 1))

        Args:
            node: The child node to compute UCB1 for.

        Returns:
            The UCB1 score as a float.
        """
        parent = node.parent
        if parent is None:
            return node.score
        parent_visits = parent.visits
        child_visits = node.visits
        if child_visits == 0:
            return float("inf")
        exploitation = node.score / (child_visits + 1)
        exploration = self.exploration_weight * math.sqrt(
            math.log(parent_visits + 1) / (child_visits + 1)
        )
        return exploitation + exploration

    def _best_path(self, node: ThoughtNode) -> list[ThoughtNode]:
        """Follow highest-scoring children from root to leaf.

        Args:
            node: The starting node (typically root).

        Returns:
            A list of ThoughtNode from the given node to the best leaf.
        """
        path: list[ThoughtNode] = [node]
        current = node
        while current.children:
            best = max(current.children, key=lambda c: c.score)
            path.append(best)
            current = best
        return path

    def _best_leaf(self, node: ThoughtNode) -> ThoughtNode:
        """Find the highest-scoring leaf node in the tree.

        Args:
            node: The starting node (typically root).

        Returns:
            The ThoughtNode with the highest score among all leaves.
        """
        best = node
        for n in self._collect_nodes(node):
            if not n.children and n.score > best.score:
                best = n
        return best

    def _path_thoughts(self, node: ThoughtNode) -> list[str]:
        """Collect thought strings from root to the given node.

        Args:
            node: The node to build the path to.

        Returns:
            A list of thought strings in order from root to node.
        """
        thoughts: list[str] = []
        current: ThoughtNode | None = node
        while current is not None:
            thoughts.insert(0, current.thought)
            current = current.parent
        return thoughts

    def _count_nodes(self, node: ThoughtNode) -> int:
        """Count total nodes in the subtree rooted at the given node.

        Args:
            node: The root of the subtree to count.

        Returns:
            The total number of nodes in the subtree.
        """
        return len(self._collect_nodes(node))

    def _collect_nodes(self, node: ThoughtNode) -> list[ThoughtNode]:
        """Collect all nodes in the subtree rooted at the given node.

        Performs a depth-first traversal to collect every node.

        Args:
            node: The root of the subtree to collect.

        Returns:
            A list of all ThoughtNode instances in the subtree.
        """
        nodes: list[ThoughtNode] = []
        stack = [node]
        while stack:
            current = stack.pop()
            nodes.append(current)
            stack.extend(current.children)
        return nodes
