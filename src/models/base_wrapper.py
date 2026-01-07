"""Base wrapper interface for all prediction models."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np

from src.utils.memory import clear_memory, unload_model

logger = logging.getLogger("ensemble")


@dataclass
class PredictionResult:
    """Result of a model prediction."""
    values: np.ndarray | None  # Predicted values
    median: float | None       # Median prediction (final value)
    quantiles: dict[float, float] | None  # Quantile predictions if available
    success: bool
    error: str | None = None
    model_name: str = ""
    horizon: str = ""


class BaseModelWrapper(ABC):
    """Abstract base class for model wrappers.

    All model wrappers must inherit from this class and implement
    the required methods.
    """

    def __init__(self, model_name: str, device: str = "cuda"):
        """Initialize wrapper.

        Args:
            model_name: HuggingFace model name or path
            device: Device to use (cuda/cpu)
        """
        self.model_name = model_name
        self.device = device
        self.model: Any = None
        self.is_loaded = False

    @abstractmethod
    def load(self) -> bool:
        """Load model into memory.

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def predict(
        self,
        data: np.ndarray,
        prediction_length: int,
    ) -> PredictionResult:
        """Make prediction on input data.

        Args:
            data: Input time series data
            prediction_length: Number of steps to predict

        Returns:
            PredictionResult with predictions
        """
        pass

    def unload(self) -> None:
        """Unload model and free memory.

        Follows CONSTITUTION.md 제13조 memory management.
        """
        if self.model is not None:
            logger.debug(f"Unloading {self.get_name()}...")
            unload_model(self.model, self.get_name())
            self.model = None
            self.is_loaded = False
            clear_memory()

    def get_name(self) -> str:
        """Get model display name.

        Returns:
            Model name string
        """
        return self.__class__.__name__.replace("Wrapper", "")

    def __enter__(self) -> "BaseModelWrapper":
        """Context manager entry."""
        self.load()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Context manager exit with cleanup."""
        self.unload()
        return False

    def is_available(self) -> bool:
        """Check if model is loaded and ready.

        Returns:
            True if model is ready for inference
        """
        return self.is_loaded and self.model is not None


def extract_median_prediction(
    predictions: np.ndarray,
    axis: int = 0,
) -> float:
    """Extract median from prediction array.

    Args:
        predictions: Array of predictions (samples x time steps)
        axis: Axis for median calculation

    Returns:
        Median of final prediction step
    """
    if predictions.ndim == 1:
        return float(predictions[-1])

    # For multi-sample predictions, take median across samples
    # and return the last time step
    if predictions.ndim == 2:
        median_trajectory = np.median(predictions, axis=axis)
        return float(median_trajectory[-1])

    return float(np.median(predictions))


def calculate_quantiles(
    predictions: np.ndarray,
    quantiles: list[float] = [0.1, 0.25, 0.5, 0.75, 0.9],
) -> dict[float, float]:
    """Calculate quantiles from prediction samples.

    Args:
        predictions: Array of prediction samples
        quantiles: List of quantile values to compute

    Returns:
        Dictionary of {quantile: value}
    """
    result = {}

    if predictions.ndim == 1:
        # Single trajectory - use last value
        for q in quantiles:
            result[q] = float(predictions[-1])
    elif predictions.ndim == 2:
        # Multiple samples - calculate quantiles at last step
        final_step = predictions[:, -1] if predictions.shape[1] > 0 else predictions[:, 0]
        for q in quantiles:
            result[q] = float(np.quantile(final_step, q))

    return result
