"""Tests for GraphRAG — in-memory knowledge graph extraction and retrieval."""

from __future__ import annotations

import pytest

from app.memory.graph_rag import GraphRAG, GraphRAGEntry, GraphRAGResult

_WORKSPACE_ID = "ws-test"
_SESSION_ID = "sess-1"


class TestGraphRAG:
    @pytest.mark.asyncio
    async def test_extract_and_store_returns_entry(self) -> None:
        graph = GraphRAG()
        text = "The ApiGateway routes requests to The DatabaseEngine for storage."

        entry = await graph.extract_and_store(_WORKSPACE_ID, _SESSION_ID, text)

        assert isinstance(entry, GraphRAGEntry)
        assert entry.workspace_id == _WORKSPACE_ID
        assert entry.session_id == _SESSION_ID
        assert "The ApiGateway" in entry.entities
        assert "The DatabaseEngine" in entry.entities
        assert len(entry.relations) > 0
        assert len(entry.context_snippet) > 0
        assert len(entry.created_at) > 0

    @pytest.mark.asyncio
    async def test_extract_entities_finds_capitalized(self) -> None:
        graph = GraphRAG()
        text = "The DataProcessor transforms raw input. The ResultValidator checks output."

        entities = graph._extract_entities(text)

        assert "The DataProcessor" in entities
        assert "The ResultValidator" in entities
        assert "raw input" not in entities

    @pytest.mark.asyncio
    async def test_extract_relations_detects_verbs(self) -> None:
        graph = GraphRAG()
        text = "The ApiGateway routes requests to The DatabaseEngine for storage."

        entities = graph._extract_entities(text)
        relations = graph._extract_relations(text, entities)

        assert any(r[1] == "routes" for r in relations)
        assert any("ApiGateway" in r[0] for r in relations)
        assert any("DatabaseEngine" in r[2] for r in relations)
        assert any(r[0] == "The ApiGateway" for r in relations)
        assert any(r[2] == "The DatabaseEngine" for r in relations)

    @pytest.mark.asyncio
    async def test_query_returns_results(self) -> None:
        graph = GraphRAG()
        await graph.extract_and_store(
            _WORKSPACE_ID,
            _SESSION_ID,
            "The ApiGateway routes requests to MicroserviceOne.",
        )

        result = await graph.query(_WORKSPACE_ID, "ApiGateway")

        assert isinstance(result, GraphRAGResult)
        assert "The ApiGateway" in result.relevant_entities

    @pytest.mark.asyncio
    async def test_query_finds_relevant_entities(self) -> None:
        graph = GraphRAG()
        await graph.extract_and_store(
            _WORKSPACE_ID,
            _SESSION_ID,
            "The CacheManager stores data. The DatabaseEngine persists records.",
        )

        result = await graph.query(_WORKSPACE_ID, "CacheManager")

        assert "The CacheManager" in result.relevant_entities
        assert "The DatabaseEngine" not in result.relevant_entities

    @pytest.mark.asyncio
    async def test_bfs_traverse_finds_relations(self) -> None:
        graph = GraphRAG()
        graph._graph.add_node("ServiceA", workspace_id=_WORKSPACE_ID)
        graph._graph.add_node("ServiceB", workspace_id=_WORKSPACE_ID)
        graph._graph.add_node("ServiceC", workspace_id=_WORKSPACE_ID)
        graph._graph.add_edge(
            "ServiceA",
            "ServiceB",
            relation="calls",
            workspace_id=_WORKSPACE_ID,
            count=1,
        )
        graph._graph.add_edge(
            "ServiceB",
            "ServiceC",
            relation="calls",
            workspace_id=_WORKSPACE_ID,
            count=1,
        )

        entities, relations, subgraph = graph._bfs_traverse(["ServiceA"])

        assert "ServiceB" in entities
        assert "ServiceC" in entities
        assert len(relations) >= 2
        assert len(subgraph) >= 1

    @pytest.mark.asyncio
    async def test_build_context_blocks_formats(self) -> None:
        graph = GraphRAG()
        entities = ["ServiceA", "ServiceB"]
        relations = [("ServiceA", "calls", "ServiceB", 0.6)]

        blocks = graph._build_context_blocks(entities, relations)

        assert any("Related entities" in b for b in blocks)
        assert any("ServiceA" in b for b in blocks)
        assert any("ServiceB" in b for b in blocks)
        assert any("calls" in b for b in blocks)

    @pytest.mark.asyncio
    async def test_clear_workspace_removes_nodes(self) -> None:
        graph = GraphRAG()
        await graph.extract_and_store(
            _WORKSPACE_ID,
            _SESSION_ID,
            "The WorkerNode processes tasks.",
        )
        await graph.extract_and_store(
            "ws-other",
            _SESSION_ID,
            "The OtherService handles requests.",
        )

        assert graph._graph.has_node("The WorkerNode")
        await graph.clear_workspace(_WORKSPACE_ID)

        assert not graph._graph.has_node("The WorkerNode")
        assert graph._graph.has_node("The OtherService")

    @pytest.mark.asyncio
    async def test_close_noop(self) -> None:
        graph = GraphRAG()
        await graph.close()

    @pytest.mark.asyncio
    async def test_entities_deduplicated(self) -> None:
        graph = GraphRAG()
        text = "The AuthService verifies users. The AuthService manages sessions."

        entry = await graph.extract_and_store(_WORKSPACE_ID, _SESSION_ID, text)

        assert entry.entities.count("The AuthService") == 1

        nodes = [
            n for n, a in graph._graph.nodes(data=True) if a.get("workspace_id") == _WORKSPACE_ID
        ]
        assert sum(1 for n in nodes if n == "The AuthService") == 1


class TestGraphRAGEdgeCases:
    @pytest.mark.asyncio
    async def test_extract_relations_empty_entities(self) -> None:
        graph = GraphRAG()
        relations = graph._extract_relations("Some text here.", [])
        assert relations == []

    @pytest.mark.asyncio
    async def test_add_duplicate_edge_increments_count(self) -> None:
        graph = GraphRAG()
        text = "The ApiGateway routes requests to The DatabaseEngine."
        await graph.extract_and_store(_WORKSPACE_ID, _SESSION_ID, text)
        await graph.extract_and_store(_WORKSPACE_ID, _SESSION_ID, text)
        # Second store should increment count on the existing edge
        edge_data = graph._graph.get_edge_data("The ApiGateway", "The DatabaseEngine")
        assert edge_data is not None
        assert edge_data.get("count", 0) > 1

    @pytest.mark.asyncio
    async def test_find_closest_entity_tie_prefers_longer(self) -> None:
        graph = GraphRAG()
        segment = "SystemManager handles requests."
        result = graph._find_closest_entity(segment, ["System", "SystemManager"])
        assert result == "SystemManager"

    @pytest.mark.asyncio
    async def test_bfs_from_leaf_hits_predecessors(self) -> None:
        graph = GraphRAG()
        graph._graph.add_node("ServiceA", workspace_id=_WORKSPACE_ID)
        graph._graph.add_node("ServiceB", workspace_id=_WORKSPACE_ID)
        graph._graph.add_edge(
            "ServiceA", "ServiceB", relation="calls", workspace_id=_WORKSPACE_ID, count=1
        )
        entities, relations, subgraph = graph._bfs_traverse(["ServiceB"])
        assert "ServiceA" in entities
        assert any("ServiceA" in str(r) for r in relations)

    @pytest.mark.asyncio
    async def test_bfs_with_cycle_skips_visited(self) -> None:
        graph = GraphRAG()
        graph._graph.add_node("NodeA", workspace_id=_WORKSPACE_ID)
        graph._graph.add_node("NodeB", workspace_id=_WORKSPACE_ID)
        graph._graph.add_node("NodeC", workspace_id=_WORKSPACE_ID)
        graph._graph.add_edge(
            "NodeA", "NodeB", relation="calls", workspace_id=_WORKSPACE_ID, count=1
        )
        graph._graph.add_edge(
            "NodeB", "NodeC", relation="calls", workspace_id=_WORKSPACE_ID, count=1
        )
        graph._graph.add_edge(
            "NodeC", "NodeA", relation="calls", workspace_id=_WORKSPACE_ID, count=1
        )
        entities, relations, subgraph = graph._bfs_traverse(["NodeA"])
        assert "NodeA" in entities
        assert "NodeB" in entities
        assert "NodeC" in entities
