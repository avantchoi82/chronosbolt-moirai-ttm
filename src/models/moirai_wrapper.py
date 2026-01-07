"""Moirai model wrapper for probabilistic time series forecasting."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import torch

from src.models.base_wrapper import (
    BaseModelWrapper,
    PredictionResult,
    calculate_quantiles,
    extract_median_prediction,
)
from src.utils.memory import get_memory_info

if TYPE_CHECKING:
    from src.utils.config_loader import ModelConfig

logger = logging.getLogger("ensemble")


class MoiraiWrapper(BaseModelWrapper):
    """Wrapper for Salesforce Moirai model.

    Based on CONSTITUTION.md 제5조 5.3:
    - Transformer Encoder architecture
    - Any-variate Attention + Masked Prediction
    - ICML 2024 Oral paper
    - Outputs sample distribution (uncertainty estimation)
    - Uses median of samples for final prediction
    """

    def __init__(
        self,
        model_name: str = "Salesforce/moirai-1.0-R-small",
        device: str = "cuda",
        num_samples: int = 100,
        patch_size: str | int = "auto",
    ):
        """Initialize Moirai wrapper.

        Args:
            model_name: HuggingFace model name
            device: Device to use
            num_samples: Number of samples for probabilistic prediction
            patch_size: Patch size ("auto" or integer)
        """
        super().__init__(model_name, device)
        self.num_samples = num_samples
        self.patch_size = patch_size

    @classmethod
    def from_config(cls, config: ModelConfig) -> "MoiraiWrapper":
        """Create wrapper from configuration.

        Args:
            config: Model configuration

        Returns:
            MoiraiWrapper instance
        """
        device = "cuda" if torch.cuda.is_available() else "cpu"
        return cls(
            model_name=config.name,
            device=device,
            num_samples=config.num_samples,
            patch_size=config.patch_size,
        )

    def load(self) -> bool:
        """Load Moirai model.

        Returns:
            True if successful
        """
        if self.is_loaded:
            return True

        try:
            from uni2ts.model.moirai import MoiraiForecast, MoiraiModule

            logger.info(f"Loading Moirai model: {self.model_name}")

            # Check device availability
            device = self.device
            if device == "cuda" and not torch.cuda.is_available():
                device = "cpu"
                logger.warning("CUDA not available, falling back to CPU")

            # Determine patch size
            patch_size = 32 if self.patch_size == "auto" else int(self.patch_size)

            # Load model
            self.module = MoiraiModule.from_pretrained(self.model_name)

            # Create forecast wrapper
            self.model = MoiraiForecast(
                module=self.module,
                prediction_length=96,  # Will be overridden per prediction
                context_length=512,     # Will be overridden per prediction
                patch_size=patch_size,
                num_samples=self.num_samples,
                target_dim=1,
                feat_dynamic_real_dim=0,
                past_feat_dynamic_real_dim=0,
            )

            # Move to device
            self.module = self.module.to(device)
            self.is_loaded = True

            mem_info = get_memory_info()
            if mem_info.cuda_available:
                logger.info(f"Moirai loaded. GPU: {mem_info.gpu_allocated:.2f}GB")
            else:
                logger.info("Moirai loaded on CPU")

            return True

        except Exception as e:
            logger.error(f"Failed to load Moirai: {e}")
            self.is_loaded = False
            return False

    def _prepare_gluonts_data(
        self,
        data: np.ndarray,
        context_length: int,
    ) -> dict:
        """Prepare data in GluonTS format for Moirai.

        Args:
            data: Input time series
            context_length: Length of context window

        Returns:
            Dictionary in GluonTS format
        """
        # Ensure we have enough data
        if len(data) < context_length:
            pad_len = context_length - len(data)
            data = np.concatenate([np.full(pad_len, data[0]), data])

        # Take last context_length points
        context_data = data[-context_length:]

        # Create GluonTS-style entry
        return {
            "target": context_data.astype(np.float32),
            "start": pd.Timestamp("2020-01-01"),  # Dummy timestamp
        }

    def predict(
        self,
        data: np.ndarray,
        prediction_length: int,
        context_length: int | None = None,
    ) -> PredictionResult:
        """Make prediction using Moirai.

        Args:
            data: Input time series
            prediction_length: Number of steps to predict
            context_length: Context window size (defaults to data length)

        Returns:
            PredictionResult with sample-based prediction
        """
        if not self.is_available():
            return PredictionResult(
                values=None,
                median=None,
                quantiles=None,
                success=False,
                error="Model not loaded",
                model_name=self.get_name(),
            )

        try:
            from uni2ts.model.moirai import MoiraiForecast

            # Determine context length
            if context_length is None:
                context_length = min(len(data), 512)

            # Determine patch size
            patch_size = 32 if self.patch_size == "auto" else int(self.patch_size)

            # Recreate forecast object with correct parameters
            device = next(self.module.parameters()).device

            forecast_model = MoiraiForecast(
                module=self.module,
                prediction_length=prediction_length,
                context_length=context_length,
                patch_size=patch_size,
                num_samples=self.num_samples,
                target_dim=1,
                feat_dynamic_real_dim=0,
                past_feat_dynamic_real_dim=0,
            )

            # Prepare input
            entry = self._prepare_gluonts_data(data, context_length)

            # Create predictor and predict
            from gluonts.dataset.common import ListDataset

            test_data = ListDataset(
                [entry],
                freq="D",
            )

            # Run prediction
            with torch.no_grad():
                predictor = forecast_model.create_predictor(batch_size=1, device=device)
                forecasts = list(predictor.predict(test_data))

            if not forecasts:
                return PredictionResult(
                    values=None,
                    median=None,
                    quantiles=None,
                    success=False,
                    error="No forecast generated",
                    model_name=self.get_name(),
                )

            # Extract samples
            forecast = forecasts[0]
            samples = forecast.samples  # Shape: (num_samples, prediction_length)

            # Calculate median (제15조)
            median_value = float(np.median(samples[:, -1]))

            # Calculate quantiles for uncertainty
            quantiles = calculate_quantiles(samples)

            return PredictionResult(
                values=samples,
                median=median_value,
                quantiles=quantiles,
                success=True,
                model_name=self.get_name(),
            )

        except Exception as e:
            logger.error(f"Moirai prediction failed: {e}")
            return PredictionResult(
                values=None,
                median=None,
                quantiles=None,
                success=False,
                error=str(e),
                model_name=self.get_name(),
            )

    def get_name(self) -> str:
        return "Moirai"

    def unload(self) -> None:
        """Unload model with additional cleanup for Moirai components."""
        if hasattr(self, 'module') and self.module is not None:
            del self.module
            self.module = None
        super().unload()
