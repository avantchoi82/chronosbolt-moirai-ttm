"""TTM (Tiny Time Mixer) model wrapper for time series forecasting."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import torch

from src.models.base_wrapper import BaseModelWrapper, PredictionResult
from src.utils.memory import get_memory_info

if TYPE_CHECKING:
    from src.utils.config_loader import ModelConfig

logger = logging.getLogger("ensemble")

# TTM model variants with their supported context/prediction lengths
TTM_VARIANTS = {
    # (context_length, prediction_length): revision
    (512, 96): "main",
    (1024, 96): "1024-96-r2",
    (1536, 96): "1536-96-r2",
}


def get_ttm_revision(context_length: int, prediction_length: int) -> str | None:
    """Get appropriate TTM model revision for given lengths.

    TTM has specific supported context/prediction length combinations.
    This function finds the best match.

    Args:
        context_length: Desired context length
        prediction_length: Desired prediction length

    Returns:
        Model revision string or None if no match
    """
    # Find best matching variant
    best_match = None
    best_context = 0

    for (ctx, pred), revision in TTM_VARIANTS.items():
        if ctx >= context_length and pred >= prediction_length:
            if best_match is None or ctx < best_context:
                best_match = revision
                best_context = ctx

    if best_match is None:
        # Use largest available
        best_match = "1536-96-r2"

    return best_match


class TTMWrapper(BaseModelWrapper):
    """Wrapper for IBM TTM (Tiny Time Mixer) model.

    Based on CONSTITUTION.md 제5조 5.2:
    - Pure MLP architecture (not Transformer)
    - Adaptive Patching
    - CPU executable, benchmark top performance
    - Point forecast output
    - IMPORTANT: Standard Scaling required for input data
    """

    # TTM minimum context length requirement
    MIN_CONTEXT_LENGTH = 512
    MAX_PREDICTION_LENGTH = 96

    def __init__(
        self,
        model_name: str = "ibm-granite/granite-timeseries-ttm-r2",
        device: str = "cuda",
        context_length: int = 512,
        prediction_length: int = 96,
    ):
        """Initialize TTM wrapper.

        Args:
            model_name: HuggingFace model name
            device: Device to use
            context_length: Input context length (will be clamped to MIN_CONTEXT_LENGTH)
            prediction_length: Prediction horizon (will be clamped to MAX_PREDICTION_LENGTH)
        """
        super().__init__(model_name, device)
        # TTM has fixed context/prediction length requirements
        self.context_length = max(context_length, self.MIN_CONTEXT_LENGTH)
        self.prediction_length = min(prediction_length, self.MAX_PREDICTION_LENGTH)
        self.requested_prediction_length = prediction_length  # Store original request
        self.revision = get_ttm_revision(self.context_length, self.prediction_length)

    @classmethod
    def from_config(
        cls,
        config: ModelConfig,
        context_length: int,
        prediction_length: int,
    ) -> "TTMWrapper":
        """Create wrapper from configuration.

        Args:
            config: Model configuration
            context_length: Input context length
            prediction_length: Prediction horizon

        Returns:
            TTMWrapper instance
        """
        device = "cuda" if torch.cuda.is_available() else "cpu"
        return cls(
            model_name=config.name,
            device=device,
            context_length=context_length,
            prediction_length=prediction_length,
        )

    def load(self) -> bool:
        """Load TTM model.

        Note: TTM loads different model variants based on
        context/prediction length requirements.

        Returns:
            True if successful
        """
        if self.is_loaded:
            return True

        try:
            from tsfm_public import TinyTimeMixerForPrediction

            logger.info(f"Loading TTM model: {self.model_name}")
            logger.debug(
                f"Context: {self.context_length}, "
                f"Prediction: {self.prediction_length}, "
                f"Revision: {self.revision}"
            )

            # Load model with appropriate revision
            self.model = TinyTimeMixerForPrediction.from_pretrained(
                self.model_name,
                revision=self.revision,
            )

            # Move to device
            device = self.device
            if device == "cuda" and not torch.cuda.is_available():
                device = "cpu"
                logger.warning("CUDA not available, falling back to CPU")

            self.model = self.model.to(device)
            self.model.eval()

            self.is_loaded = True

            mem_info = get_memory_info()
            if mem_info.cuda_available:
                logger.info(f"TTM loaded. GPU: {mem_info.gpu_allocated:.2f}GB")
            else:
                logger.info("TTM loaded on CPU")

            return True

        except Exception as e:
            logger.error(f"Failed to load TTM: {e}")
            self.is_loaded = False
            return False

    def predict(
        self,
        data: np.ndarray,
        prediction_length: int,
    ) -> PredictionResult:
        """Make prediction using TTM.

        IMPORTANT: Input data should already be Standard Scaled!
        The output will be in the same scaled space.

        Args:
            data: Input time series (should be normalized)
            prediction_length: Number of steps to predict

        Returns:
            PredictionResult with point forecast
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
            # Prepare input tensor
            # TTM expects shape: (batch, sequence, channels)
            if len(data) < self.context_length:
                # Pad with first value
                pad_len = self.context_length - len(data)
                data = np.concatenate([np.full(pad_len, data[0]), data])

            # Take last context_length points
            input_data = data[-self.context_length:]

            # Reshape for model: (1, context_length, 1)
            input_tensor = torch.tensor(
                input_data.reshape(1, -1, 1),
                dtype=torch.float32,
            )

            # Move to device
            device = next(self.model.parameters()).device
            input_tensor = input_tensor.to(device)

            # Run inference
            with torch.no_grad():
                output = self.model(input_tensor)

            # Extract predictions
            # Output shape: (batch, prediction_length, channels)
            predictions = output.prediction_outputs
            pred_np = predictions[0, :, 0].cpu().numpy()

            # Trim to requested prediction length
            # Use the stored requested_prediction_length if it's smaller than model output
            target_length = min(prediction_length, len(pred_np))
            pred_np = pred_np[:target_length]

            # TTM outputs point forecast, so median = last value
            median_value = float(pred_np[-1])

            return PredictionResult(
                values=pred_np,
                median=median_value,
                quantiles=None,  # TTM doesn't provide quantiles
                success=True,
                model_name=self.get_name(),
            )

        except Exception as e:
            logger.error(f"TTM prediction failed: {e}")
            return PredictionResult(
                values=None,
                median=None,
                quantiles=None,
                success=False,
                error=str(e),
                model_name=self.get_name(),
            )

    def get_name(self) -> str:
        return "TTM"


class TTMHorizonManager:
    """Manager for loading different TTM models per horizon.

    As per CONSTITUTION.md 제12조 Phase 2:
    TTM requires separate model loading for each horizon.
    """

    def __init__(self, model_name: str = "ibm-granite/granite-timeseries-ttm-r2"):
        """Initialize manager.

        Args:
            model_name: Base HuggingFace model name
        """
        self.model_name = model_name
        self.current_wrapper: TTMWrapper | None = None
        self.current_horizon: str | None = None

    def get_wrapper(
        self,
        context_length: int,
        prediction_length: int,
        horizon_name: str,
    ) -> TTMWrapper:
        """Get TTM wrapper for specific horizon.

        Loads new model if horizon changed, otherwise returns cached.

        Args:
            context_length: Input context length
            prediction_length: Prediction horizon
            horizon_name: Horizon identifier (short/mid/long)

        Returns:
            Loaded TTMWrapper
        """
        # Check if we need to load a different model
        if (
            self.current_horizon != horizon_name
            or self.current_wrapper is None
        ):
            # Unload current model first
            if self.current_wrapper is not None:
                self.current_wrapper.unload()

            # Create and load new wrapper
            self.current_wrapper = TTMWrapper(
                model_name=self.model_name,
                context_length=context_length,
                prediction_length=prediction_length,
            )
            self.current_wrapper.load()
            self.current_horizon = horizon_name

        return self.current_wrapper

    def unload(self) -> None:
        """Unload current model."""
        if self.current_wrapper is not None:
            self.current_wrapper.unload()
            self.current_wrapper = None
            self.current_horizon = None
