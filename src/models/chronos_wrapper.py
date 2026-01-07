"""Chronos-Bolt model wrapper for time series forecasting."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
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


class ChronosWrapper(BaseModelWrapper):
    """Wrapper for Amazon Chronos-Bolt model.

    Based on CONSTITUTION.md 제5조 5.1:
    - T5-based Encoder-Decoder architecture
    - Patch-based multi-step prediction
    - Outputs probability distribution (quantiles)
    - Uses 50% quantile (median) for final prediction
    """

    def __init__(
        self,
        model_name: str = "amazon/chronos-bolt-small",
        device: str = "cuda",
        dtype: str = "bfloat16",
    ):
        """Initialize Chronos wrapper.

        Args:
            model_name: HuggingFace model name
            device: Device to use
            dtype: Model dtype (bfloat16 recommended)
        """
        super().__init__(model_name, device)
        self.dtype = dtype
        self.pipeline = None

    @classmethod
    def from_config(cls, config: ModelConfig) -> "ChronosWrapper":
        """Create wrapper from configuration.

        Args:
            config: Model configuration

        Returns:
            ChronosWrapper instance
        """
        device = "cuda" if torch.cuda.is_available() else "cpu"
        return cls(
            model_name=config.name,
            device=device,
            dtype=config.dtype,
        )

    def load(self) -> bool:
        """Load Chronos model.

        Returns:
            True if successful
        """
        if self.is_loaded:
            return True

        try:
            # Use ChronosBoltPipeline for bolt models, ChronosPipeline for others
            if "bolt" in self.model_name.lower():
                from chronos import ChronosBoltPipeline as Pipeline
            else:
                from chronos import ChronosPipeline as Pipeline

            # Determine dtype
            torch_dtype = torch.bfloat16 if self.dtype == "bfloat16" else torch.float32

            # Check device availability
            device = self.device
            if device == "cuda" and not torch.cuda.is_available():
                device = "cpu"
                logger.warning("CUDA not available, falling back to CPU")

            logger.info(f"Loading Chronos model: {self.model_name}")
            logger.debug(f"Device: {device}, dtype: {self.dtype}")

            self.pipeline = Pipeline.from_pretrained(
                self.model_name,
                device_map=device,
                torch_dtype=torch_dtype,
            )

            self.model = self.pipeline
            self.is_loaded = True

            mem_info = get_memory_info()
            if mem_info.cuda_available:
                logger.info(f"Chronos loaded. GPU: {mem_info.gpu_allocated:.2f}GB")

            return True

        except Exception as e:
            logger.error(f"Failed to load Chronos: {e}")
            self.is_loaded = False
            return False

    def predict(
        self,
        data: np.ndarray,
        prediction_length: int,
    ) -> PredictionResult:
        """Make prediction using Chronos.

        Args:
            data: Input time series (1D array)
            prediction_length: Number of steps to predict

        Returns:
            PredictionResult with median prediction
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
            # Convert to tensor
            input_tensor = torch.tensor(data, dtype=torch.float32)

            # Run prediction
            with torch.no_grad():
                # ChronosBoltPipeline uses 'inputs', ChronosPipeline uses 'context'
                if "bolt" in self.model_name.lower():
                    # ChronosBolt returns (batch, num_quantiles, pred_len)
                    forecast = self.pipeline.predict(
                        inputs=input_tensor,
                        prediction_length=prediction_length,
                    )
                    # Take median quantile (index 4 for 9 quantiles: 0.1-0.9)
                    forecast_np = forecast.numpy()
                    if forecast_np.ndim == 3:
                        # Shape: (1, num_quantiles, pred_len) -> take median quantile
                        median_idx = forecast_np.shape[1] // 2  # Middle quantile
                        median_trajectory = forecast_np[0, median_idx, :]
                        median_value = float(median_trajectory[-1])
                    else:
                        median_value = float(forecast_np.flatten()[-1])
                else:
                    # Standard Chronos returns samples
                    forecast = self.pipeline.predict(
                        context=input_tensor,
                        prediction_length=prediction_length,
                    )
                    forecast_np = forecast.numpy()
                    median_value = extract_median_prediction(forecast_np)

            # Calculate quantiles for uncertainty estimation
            quantiles = calculate_quantiles(forecast_np)

            return PredictionResult(
                values=forecast_np,
                median=median_value,
                quantiles=quantiles,
                success=True,
                model_name=self.get_name(),
            )

        except Exception as e:
            logger.error(f"Chronos prediction failed: {e}")
            return PredictionResult(
                values=None,
                median=None,
                quantiles=None,
                success=False,
                error=str(e),
                model_name=self.get_name(),
            )

    def predict_batch(
        self,
        data_list: list[np.ndarray],
        prediction_length: int,
    ) -> list[PredictionResult]:
        """Make predictions for multiple time series.

        Args:
            data_list: List of input time series
            prediction_length: Number of steps to predict

        Returns:
            List of PredictionResults
        """
        if not self.is_available():
            return [
                PredictionResult(
                    values=None,
                    median=None,
                    quantiles=None,
                    success=False,
                    error="Model not loaded",
                    model_name=self.get_name(),
                )
                for _ in data_list
            ]

        results = []

        try:
            # Convert all to tensors
            contexts = [torch.tensor(d, dtype=torch.float32) for d in data_list]

            with torch.no_grad():
                forecasts = self.pipeline.predict(
                    context=contexts,
                    prediction_length=prediction_length,
                )

            # Process each forecast
            for i, forecast in enumerate(forecasts):
                forecast_np = forecast.numpy()
                median_value = extract_median_prediction(forecast_np)
                quantiles = calculate_quantiles(forecast_np)

                results.append(PredictionResult(
                    values=forecast_np,
                    median=median_value,
                    quantiles=quantiles,
                    success=True,
                    model_name=self.get_name(),
                ))

        except Exception as e:
            logger.error(f"Chronos batch prediction failed: {e}")
            # Return failure for all
            for _ in data_list:
                results.append(PredictionResult(
                    values=None,
                    median=None,
                    quantiles=None,
                    success=False,
                    error=str(e),
                    model_name=self.get_name(),
                ))

        return results

    def get_name(self) -> str:
        return "Chronos"
