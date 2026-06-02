"""VRAM manager for GPU memory budget tracking and model selection."""

from __future__ import annotations

from typing import Final

from app.utils.llm_router import WorkType

MODEL_VRAM_COSTS: Final[dict[str, float]] = {
    "qwen2.5:7b-instruct-q4_K_M": 4.5,
    "qwen2.5:7b-instruct-q8_0": 7.0,
    "llama3.1:8b-q4_K_M": 5.0,
    "llama3.1:8b-q8_0": 8.0,
    "deepseek-coder:6.7b-q4_K_M": 4.0,
    "deepseek-coder:6.7b-q8_0": 6.5,
    "nomic-embed-text": 0.5,
}

DEFAULT_VRAM_COST: Final[float] = 6.0

_WORK_TYPE_MODEL_MAP: Final[dict[WorkType, str]] = {
    WorkType.CODE_GEN: "deepseek-coder:6.7b-q4_K_M",
    WorkType.CODE_AGENT: "deepseek-coder:6.7b-q4_K_M",
    WorkType.REASONING: "llama3.1:8b-q4_K_M",
    WorkType.CONTENT: "qwen2.5:7b-instruct-q4_K_M",
    WorkType.FAST: "qwen2.5:7b-instruct-q4_K_M",
    WorkType.MULTIMODAL: "llama3.1:8b-q4_K_M",
    WorkType.DEBUG: "qwen2.5:7b-instruct-q4_K_M",
    WorkType.GENERAL: "qwen2.5:7b-instruct-q4_K_M",
}

_MODEL_FALLBACK_CHAIN: Final[dict[str, str]] = {
    "deepseek-coder:6.7b-q8_0": "deepseek-coder:6.7b-q4_K_M",
    "llama3.1:8b-q8_0": "llama3.1:8b-q4_K_M",
    "llama3.1:8b-q4_K_M": "qwen2.5:7b-instruct-q4_K_M",
    "qwen2.5:7b-instruct-q8_0": "qwen2.5:7b-instruct-q4_K_M",
    "qwen2.5:7b-instruct-q4_K_M": "nomic-embed-text",
    "deepseek-coder:6.7b-q4_K_M": "nomic-embed-text",
}


class VRAMManager:
    """Tracks and manages VRAM budget for GPU model loading.

    Attributes:
        total_vram_gb: Total available VRAM in GB.
    """

    def __init__(self, total_vram_gb: float = 12.0) -> None:
        """Initialise the VRAM manager with a total budget.

        Args:
            total_vram_gb: Total VRAM budget in GB. Defaults to 12.0.
        """
        self.total_vram_gb: float = total_vram_gb
        self._allocations: dict[str, float] = {}

    @staticmethod
    def get_vram_cost(model_name: str) -> float:
        """Return the VRAM cost in GB for a given model name.

        Args:
            model_name: The model identifier string.

        Returns:
            VRAM cost in GB. Falls back to 6.0 GB for unknown models.
        """
        return MODEL_VRAM_COSTS.get(model_name, DEFAULT_VRAM_COST)

    def get_usage_gb(self) -> float:
        """Return the total VRAM currently allocated in GB.

        Returns:
            Currently used VRAM in GB.
        """
        return sum(self._allocations.values())

    def get_available_gb(self) -> float:
        """Return the remaining available VRAM in GB.

        Returns:
            Available VRAM in GB.
        """
        return self.total_vram_gb - self.get_usage_gb()

    def can_load(self, model_name: str) -> bool:
        """Check whether a model can be loaded within the remaining VRAM budget.

        Args:
            model_name: The model identifier string.

        Returns:
            True if the model fits, False otherwise.
        """
        return self.get_vram_cost(model_name) <= self.get_available_gb()

    def reserve(self, model_name: str) -> bool:
        """Reserve VRAM for a model if sufficient budget remains.

        Args:
            model_name: The model identifier string.

        Returns:
            True if VRAM was reserved, False if insufficient budget.
        """
        if not self.can_load(model_name):
            return False
        cost = self.get_vram_cost(model_name)
        current = self._allocations.get(model_name, 0.0)
        self._allocations[model_name] = current + cost
        return True

    def release(self, model_name: str) -> None:
        """Release all VRAM allocated to a model.

        Args:
            model_name: The model identifier string.
        """
        self._allocations.pop(model_name, None)

    def reset(self) -> None:
        """Reset all VRAM allocations, freeing the entire budget."""
        self._allocations.clear()

    def get_best_model(
        self,
        work_type: str,
        preferred: str | None = None,
    ) -> str:
        """Return the best model that fits in the current VRAM budget.

        Tries the preferred model first, then the default model for the
        work type, then walks the fallback chain to lighter quantisations.
        Returns ``nomic-embed-text`` (0.5 GB) as the last resort.

        Args:
            work_type: The work type string matching a ``WorkType`` value.
            preferred: An optional preferred model name to try first.

        Returns:
            The name of the best model that fits.
        """
        wt = WorkType(work_type)
        default = _WORK_TYPE_MODEL_MAP.get(wt, "qwen2.5:7b-instruct-q4_K_M")

        seen: set[str] = set()
        candidates: list[str] = []
        if preferred and preferred not in seen:
            candidates.append(preferred)
            seen.add(preferred)
        if default not in seen:
            candidates.append(default)
            seen.add(default)

        for model in candidates:
            if self.can_load(model):
                return model

        current = default
        while current in _MODEL_FALLBACK_CHAIN:
            current = _MODEL_FALLBACK_CHAIN[current]
            if current in seen:
                continue
            seen.add(current)
            if self.can_load(current):
                return current

        return "nomic-embed-text"
