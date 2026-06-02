"""Tests for VRAMManager — GPU memory budget tracking and model selection."""

from __future__ import annotations

import pytest

from app.utils.vram_manager import (
    MODEL_VRAM_COSTS,
    VRAMManager,
)


class TestInit:
    def test_init_default_vram(self) -> None:
        manager = VRAMManager()
        assert manager.total_vram_gb == 12.0

    def test_init_custom_vram(self) -> None:
        manager = VRAMManager(total_vram_gb=24.0)
        assert manager.total_vram_gb == 24.0


class TestCanLoad:
    def test_can_load_true(self) -> None:
        manager = VRAMManager()
        assert manager.can_load("qwen2.5:7b-instruct-q4_K_M")

    def test_can_load_false(self) -> None:
        manager = VRAMManager(total_vram_gb=4.0)
        manager.reserve("llama3.1:8b-q4_K_M")
        assert not manager.can_load("llama3.1:8b-q4_K_M")

    def test_can_load_exact_budget(self) -> None:
        manager = VRAMManager(total_vram_gb=4.5)
        assert manager.can_load("qwen2.5:7b-instruct-q4_K_M")

    def test_can_load_over_budget(self) -> None:
        manager = VRAMManager(total_vram_gb=4.4)
        assert not manager.can_load("qwen2.5:7b-instruct-q4_K_M")


class TestReserve:
    def test_reserve_success(self) -> None:
        manager = VRAMManager()
        assert manager.reserve("qwen2.5:7b-instruct-q4_K_M")

    def test_reserve_failure(self) -> None:
        manager = VRAMManager(total_vram_gb=2.0)
        assert not manager.reserve("llama3.1:8b-q4_K_M")

    def test_reserve_multiple_same_model(self) -> None:
        manager = VRAMManager(total_vram_gb=10.0)
        assert manager.reserve("qwen2.5:7b-instruct-q4_K_M")
        assert manager.reserve("qwen2.5:7b-instruct-q4_K_M")
        assert manager.get_usage_gb() == pytest.approx(9.0)

    def test_reserve_returns_false_when_full(self) -> None:
        manager = VRAMManager(total_vram_gb=1.0)
        assert not manager.reserve("llama3.1:8b-q4_K_M")


class TestRelease:
    def test_release_frees_vram(self) -> None:
        manager = VRAMManager()
        manager.reserve("qwen2.5:7b-instruct-q4_K_M")
        assert manager.get_usage_gb() == pytest.approx(4.5)
        manager.release("qwen2.5:7b-instruct-q4_K_M")
        assert manager.get_usage_gb() == pytest.approx(0.0)

    def test_release_unknown_model_does_nothing(self) -> None:
        manager = VRAMManager()
        manager.reserve("qwen2.5:7b-instruct-q4_K_M")
        manager.release("nonexistent-model")
        assert manager.get_usage_gb() == pytest.approx(4.5)

    def test_release_frees_space_for_other(self) -> None:
        manager = VRAMManager(total_vram_gb=6.0)
        manager.reserve("qwen2.5:7b-instruct-q4_K_M")
        assert not manager.can_load("llama3.1:8b-q4_K_M")
        manager.release("qwen2.5:7b-instruct-q4_K_M")
        assert manager.can_load("llama3.1:8b-q4_K_M")


class TestReset:
    def test_reset_clears_all(self) -> None:
        manager = VRAMManager()
        manager.reserve("qwen2.5:7b-instruct-q4_K_M")
        manager.reserve("nomic-embed-text")
        manager.reset()
        assert manager.get_usage_gb() == pytest.approx(0.0)
        assert manager.get_available_gb() == pytest.approx(12.0)

    def test_reset_empty_manager(self) -> None:
        manager = VRAMManager()
        manager.reset()
        assert manager.get_usage_gb() == pytest.approx(0.0)


class TestQuery:
    def test_get_available_gb(self) -> None:
        manager = VRAMManager(total_vram_gb=12.0)
        assert manager.get_available_gb() == pytest.approx(12.0)
        manager.reserve("nomic-embed-text")
        assert manager.get_available_gb() == pytest.approx(11.5)

    def test_get_usage_gb(self) -> None:
        manager = VRAMManager()
        assert manager.get_usage_gb() == pytest.approx(0.0)
        manager.reserve("qwen2.5:7b-instruct-q4_K_M")
        assert manager.get_usage_gb() == pytest.approx(4.5)
        manager.reserve("nomic-embed-text")
        assert manager.get_usage_gb() == pytest.approx(5.0)

    def test_get_usage_gb_after_release(self) -> None:
        manager = VRAMManager()
        manager.reserve("qwen2.5:7b-instruct-q4_K_M")
        manager.reserve("nomic-embed-text")
        manager.release("qwen2.5:7b-instruct-q4_K_M")
        assert manager.get_usage_gb() == pytest.approx(0.5)


class TestGetBestModel:
    def test_get_best_model_preferred(self) -> None:
        manager = VRAMManager()
        model = manager.get_best_model("code_gen", preferred="deepseek-coder:6.7b-q8_0")
        assert model == "deepseek-coder:6.7b-q8_0"

    def test_get_best_model_fallback(self) -> None:
        manager = VRAMManager(total_vram_gb=1.0)
        model = manager.get_best_model("code_gen", preferred="llama3.1:8b-q4_K_M")
        assert model == "nomic-embed-text"

    def test_get_best_model_default_when_preferred_too_big(self) -> None:
        manager = VRAMManager(total_vram_gb=5.0)
        model = manager.get_best_model("code_gen", preferred="llama3.1:8b-q8_0")
        assert model == "deepseek-coder:6.7b-q4_K_M"

    def test_get_best_model_walks_fallback_chain(self) -> None:
        manager = VRAMManager(total_vram_gb=1.0)
        model = manager.get_best_model("reasoning", preferred="llama3.1:8b-q8_0")
        assert model == "nomic-embed-text"

    def test_get_best_model_no_preferred(self) -> None:
        manager = VRAMManager()
        model = manager.get_best_model("content")
        assert model == "qwen2.5:7b-instruct-q4_K_M"

    def test_get_best_model_returns_nomic_as_last_resort(self) -> None:
        manager = VRAMManager(total_vram_gb=0.1)
        model = manager.get_best_model("general", preferred="llama3.1:8b-q8_0")
        assert model == "nomic-embed-text"


class TestVramCost:
    def test_vram_cost_known_model(self) -> None:
        assert VRAMManager.get_vram_cost("qwen2.5:7b-instruct-q4_K_M") == 4.5

    def test_vram_cost_unknown_model(self) -> None:
        assert VRAMManager.get_vram_cost("unknown-model-42b") == 6.0

    def test_vram_cost_all_known(self) -> None:
        for model, cost in MODEL_VRAM_COSTS.items():
            assert VRAMManager.get_vram_cost(model) == cost


class TestFullWorkflow:
    def test_full_workflow(self) -> None:
        manager = VRAMManager(total_vram_gb=10.0)
        assert manager.get_available_gb() == pytest.approx(10.0)
        assert manager.get_usage_gb() == pytest.approx(0.0)
        assert manager.reserve("qwen2.5:7b-instruct-q4_K_M")
        assert manager.get_usage_gb() == pytest.approx(4.5)
        assert manager.get_available_gb() == pytest.approx(5.5)
        assert manager.reserve("nomic-embed-text")
        assert manager.get_usage_gb() == pytest.approx(5.0)
        assert manager.get_available_gb() == pytest.approx(5.0)
        manager.release("qwen2.5:7b-instruct-q4_K_M")
        assert manager.get_usage_gb() == pytest.approx(0.5)
        assert manager.get_available_gb() == pytest.approx(9.5)
        assert manager.can_load("deepseek-coder:6.7b-q8_0")
        manager.reset()
        assert manager.get_usage_gb() == pytest.approx(0.0)
        assert manager.get_available_gb() == pytest.approx(10.0)
