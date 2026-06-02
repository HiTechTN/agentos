"""GraphRAG — graph-based retrieval augmented generation using NetworkX.

Stores entities and relations extracted from task sessions as a
knowledge graph, and retrieves relevant context via graph traversal.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import networkx as nx

from app.utils.logging import get_logger

logger = get_logger(__name__)

_VERBS = frozenset(
    {
        "uses",
        "implements",
        "calls",
        "creates",
        "sends",
        "receives",
        "processes",
        "stores",
        "validates",
        "invokes",
        "handles",
        "generates",
        "parses",
        "transforms",
        "routes",
        "deploys",
        "configures",
        "monitors",
        "authenticates",
        "authorizes",
        "encrypts",
        "decrypts",
        "compiles",
        "tests",
    }
)


@dataclass
class GraphRAGEntry:
    """Record of a single extraction operation stored in the graph."""

    id: str
    workspace_id: str
    session_id: str
    entities: list[str] = field(default_factory=list)
    relations: list[tuple[str, str, str]] = field(default_factory=list)
    context_snippet: str = ""
    created_at: str = ""


@dataclass
class GraphRAGResult:
    """Result of a graph-based retrieval query."""

    relevant_entities: list[str] = field(default_factory=list)
    relevant_relations: list[tuple[str, str, str, float]] = field(default_factory=list)
    context_blocks: list[str] = field(default_factory=list)
    subgraph: dict[str, Any] = field(default_factory=dict)


class GraphRAG:
    """In-memory knowledge graph for entity-relation extraction and traversal.

    Uses a NetworkX DiGraph as the working store. Nodes represent entities
    with workspace_id attributes; edges represent directed relations with
    a relation type label.
    """

    def __init__(self) -> None:
        self._graph: nx.DiGraph = nx.DiGraph()

    async def close(self) -> None:
        """Clean up resources. No-op for in-memory graph."""

    async def clear_workspace(self, workspace_id: str) -> None:
        """Remove all nodes and edges associated with a workspace."""
        nodes_to_remove = [
            n
            for n, attrs in self._graph.nodes(data=True)
            if attrs.get("workspace_id") == workspace_id
        ]
        self._graph.remove_nodes_from(nodes_to_remove)
        logger.log_action(
            agent_id="graph_rag",
            action="workspace_cleared",
            status="completed",
            details={"workspace_id": workspace_id, "nodes_removed": len(nodes_to_remove)},
        )

    async def extract_and_store(
        self,
        workspace_id: str,
        session_id: str,
        text: str,
    ) -> GraphRAGEntry:
        """Extract entities and relations from text and store in the graph.

        Args:
            workspace_id: Scoping identifier for the workspace.
            session_id: Scoping identifier for the session.
            text: Raw text content to analyse.

        Returns:
            A GraphRAGEntry describing what was extracted and stored.
        """
        entities = self._extract_entities(text)
        relations = self._extract_relations(text, entities)

        entry_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        context_snippet = text[:300]

        for entity in entities:
            if not self._graph.has_node(entity):
                self._graph.add_node(
                    entity,
                    workspace_id=workspace_id,
                    first_seen=now,
                )

        for source, relation, target in relations:
            edge_data = self._graph.get_edge_data(source, target)
            if edge_data is None:
                self._graph.add_edge(
                    source,
                    target,
                    relation=relation,
                    workspace_id=workspace_id,
                    first_seen=now,
                    count=1,
                )
            else:
                self._graph.add_edge(
                    source,
                    target,
                    relation=relation,
                    workspace_id=workspace_id,
                    first_seen=edge_data.get("first_seen", now),
                    count=edge_data.get("count", 0) + 1,
                )

        logger.log_action(
            agent_id="graph_rag",
            action="extract_and_store",
            status="completed",
            details={
                "entry_id": entry_id,
                "workspace_id": workspace_id,
                "entities_count": len(entities),
                "relations_count": len(relations),
            },
        )

        return GraphRAGEntry(
            id=entry_id,
            workspace_id=workspace_id,
            session_id=session_id,
            entities=entities,
            relations=relations,
            context_snippet=context_snippet,
            created_at=now,
        )

    async def query(
        self,
        workspace_id: str,
        query: str,
        max_entities: int = 10,
    ) -> GraphRAGResult:
        """Search entities by keyword matching and traverse the graph.

        Args:
            workspace_id: Only consider entities from this workspace.
            query: Free-text query to match against entity names.
            max_entities: Maximum seed entities to use for traversal.

        Returns:
            A GraphRAGResult with relevant entities, relations, context
            blocks and the serialised subgraph.
        """
        workspace_nodes = [
            n
            for n, attrs in self._graph.nodes(data=True)
            if attrs.get("workspace_id") == workspace_id
        ]

        query_lower = query.lower()
        query_tokens = query_lower.split()
        scored: list[tuple[str, float]] = []

        for node in workspace_nodes:
            node_lower = node.lower()
            score = 0.0
            for token in query_tokens:
                if token in node_lower:
                    score += 1.0
                if node_lower.startswith(token) or node_lower.endswith(token):
                    score += 0.5
                if any(token in phrase for phrase in node_lower.split()):
                    score += 0.3
            if score > 0:
                scored.append((node, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        seed_entities = [n for n, _ in scored[:max_entities]]

        entities, relations, subgraph = self._bfs_traverse(seed_entities)
        context_blocks = self._build_context_blocks(entities, relations)

        return GraphRAGResult(
            relevant_entities=entities,
            relevant_relations=relations,
            context_blocks=context_blocks,
            subgraph=subgraph,
        )

    def _extract_entities(self, text: str) -> list[str]:
        """Extract unique entity candidates from text.

        Splits text into sentences and collects 2-4 word title-cased
        n-grams as potential entities.

        Args:
            text: Raw text content.

        Returns:
            Sorted list of unique entity strings.
        """
        sentences = [
            s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()
        ]
        candidates: set[str] = set()

        for sentence in sentences:
            words = sentence.split()
            for n in range(2, min(5, len(words) + 1)):
                for i in range(len(words) - n + 1):
                    phrase = " ".join(words[i : i + n])
                    if phrase[0].isupper() and all(
                        w[0].isupper() if w else True for w in words[i : i + n]
                    ):
                        cleaned = phrase.strip(" ,;:!?\"'()[]{}=+*/\\|<>@#$%^&~`")
                        if cleaned and len(cleaned) > 2:
                            candidates.add(cleaned)

        return sorted(candidates)

    def _extract_relations(
        self,
        text: str,
        entities: list[str],
    ) -> list[tuple[str, str, str]]:
        """Extract verb-based relations between known entities.

        Splits text on known action verbs and pairs the surrounding
        entity mentions as (source, verb, target) triples.

        Args:
            text: Raw text content.
            entities: Entity names to link.

        Returns:
            List of (source, relation, target) triples.
        """
        if not entities:
            return []

        relations: list[tuple[str, str, str]] = []
        seen: set[tuple[str, str, str]] = set()

        sentences = [
            s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()
        ]

        for sentence in sentences:
            lower_sent = sentence.lower()
            for verb in _VERBS:
                if verb not in lower_sent:
                    continue
                parts = lower_sent.split(verb, 1)
                if len(parts) < 2:
                    continue
                before = parts[0].strip()
                after = parts[1].strip()

                source = self._find_closest_entity(before, entities)
                target = self._find_closest_entity(after, entities)

                if source and target and source != target:
                    triple = (source, verb, target)
                    if triple not in seen:
                        seen.add(triple)
                        relations.append(triple)

        return relations

    def _find_closest_entity(self, segment: str, entities: list[str]) -> str | None:
        """Return the last entity mention in a text segment.

        Matches entities by checking if any entity name appears as a
        substring of the segment and returns the one with the latest
        start position.

        Args:
            segment: Text segment to search within.
            entities: Candidate entity names.

        Returns:
            The closest matching entity name, or None if no match.
        """
        segment_lower = segment.lower()
        best: tuple[str | None, int] = (None, -1)
        for entity in entities:
            entity_lower = entity.lower()
            pos = segment_lower.rfind(entity_lower)
            if pos > best[1]:
                best = (entity, pos)
            elif pos == best[1] and pos >= 0 and len(entity) > len(best[0] or ""):
                best = (entity, pos)
        return best[0]

    def _bfs_traverse(
        self,
        seed_entities: list[str],
        max_depth: int = 2,
    ) -> tuple[list[str], list[tuple[str, str, str, float]], dict[str, Any]]:
        """Breadth-first traversal from seed entities.

        Explores the graph up to max_depth hops, collecting reached
        entities, relations with a confidence score, and a serialisable
        subgraph representation.

        Args:
            seed_entities: Starting nodes for traversal.
            max_depth: Maximum number of edges to traverse.

        Returns:
            Tuple of (attained entities, (src, rel, tgt, score) tuples,
            serialised subgraph adjacency dict).
        """
        reached: set[str] = set()
        edges: set[tuple[str, str, str, float]] = set()
        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(e, 0) for e in seed_entities if self._graph.has_node(e)]

        for entity, depth in queue:
            if entity in visited or depth > max_depth:
                continue
            visited.add(entity)
            reached.add(entity)

            if depth < max_depth:
                for neighbor in self._graph.successors(entity):
                    edge = self._graph.get_edge_data(entity, neighbor)
                    if edge:
                        rel = edge.get("relation", "related_to")
                        score = min(1.0, 0.5 + 0.1 * (edge.get("count", 1) - 1))
                        edges.add((entity, rel, neighbor, score))
                    if neighbor not in visited:
                        queue.append((neighbor, depth + 1))

                for neighbor in self._graph.predecessors(entity):
                    edge = self._graph.get_edge_data(neighbor, entity)
                    if edge:
                        rel = edge.get("relation", "related_to")
                        score = min(1.0, 0.5 + 0.1 * (edge.get("count", 1) - 1))
                        edges.add((neighbor, rel, entity, score))
                    if neighbor not in visited:
                        queue.append((neighbor, depth + 1))

        subgraph: dict[str, Any] = {}
        for node in reached:
            neighbors: dict[str, list[dict[str, Any]]] = {}
            for nbr in self._graph.successors(node):
                if nbr in reached:
                    edge_data = self._graph.get_edge_data(node, nbr)
                    neighbors.setdefault(nbr, []).append(
                        {"relation": edge_data.get("relation", "related_to")} if edge_data else {}
                    )
            for nbr in self._graph.predecessors(node):
                if nbr in reached:
                    edge_data = self._graph.get_edge_data(nbr, node)
                    neighbors.setdefault(nbr, []).append(
                        {"relation": edge_data.get("relation", "related_to")} if edge_data else {}
                    )
            subgraph[node] = neighbors

        return sorted(reached), sorted(edges), subgraph

    def _build_context_blocks(
        self,
        entities: list[str],
        relations: list[tuple[str, str, str, float]],
    ) -> list[str]:
        """Format traversal results as human-readable context strings.

        Args:
            entities: Entity names to include.
            relations: (source, relation, target, score) tuples.

        Returns:
            List of formatted context block strings.
        """
        blocks: list[str] = []

        if entities:
            entity_line = "Related entities: " + ", ".join(entities)
            blocks.append(entity_line)

        if relations:
            rel_lines: list[str] = []
            for source, relation, target, score in relations:
                rel_lines.append(f"  {source} --[{relation}]--> {target}  (score={score:.2f})")
            if rel_lines:
                blocks.append("Relations:\n" + "\n".join(rel_lines))

        return blocks
