"""Inference orchestrator for multi-model ensemble prediction."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from tqdm import tqdm

from src.data.preprocessor import StandardScaler, prepare_model_input, get_current_price
from src.models.chronos_wrapper import ChronosWrapper
from src.models.moirai_wrapper import MoiraiWrapper
from src.models.ttm_wrapper import TTMWrapper, TTMHorizonManager
from src.utils.memory import clear_memory, get_memory_info

if TYPE_CHECKING:
    import pandas as pd
    from src.utils.config_loader import Config, HorizonConfig

logger = logging.getLogger("ensemble")


@dataclass
class HorizonPrediction:
    """Prediction result for a single horizon."""
    horizon: str
    prediction_length: int
    predicted_price: float | None
    current_price: float
    raw_return: float | None = None
    success: bool = True
    error: str | None = None


@dataclass
class ModelPredictions:
    """Predictions from a single model across all horizons."""
    model_name: str
    horizons: dict[str, HorizonPrediction] = field(default_factory=dict)


@dataclass
class StockPredictions:
    """All predictions for a single stock."""
    code: str
    current_price: float
    models: dict[str, ModelPredictions] = field(default_factory=dict)

    def get_prediction(self, model: str, horizon: str) -> float | None:
        """Get predicted price for model/horizon."""
        if model in self.models and horizon in self.models[model].horizons:
            return self.models[model].horizons[horizon].predicted_price
        return None

    def get_return(self, model: str, horizon: str) -> float | None:
        """Get raw return for model/horizon."""
        if model in self.models and horizon in self.models[model].horizons:
            hp = self.models[model].horizons[horizon]
            if hp.predicted_price is not None:
                return (hp.predicted_price - self.current_price) / self.current_price
        return None


class InferenceEngine:
    """Orchestrator for multi-model inference.

    Follows CONSTITUTION.md 제12조 execution order:
    - Phase 1: Chronos-Bolt (all horizons at once)
    - Phase 2: TTM (load/unload per horizon)
    - Phase 3: Moirai (all horizons at once)
    """

    def __init__(self, config: Config):
        """Initialize inference engine.

        Args:
            config: Configuration object
        """
        self.config = config
        self.results: dict[str, StockPredictions] = {}

    def run_inference(
        self,
        data_dict: dict[str, pd.DataFrame],
        progress_callback: callable | None = None,
    ) -> dict[str, StockPredictions]:
        """Run full inference pipeline.

        Args:
            data_dict: Dictionary of {code: DataFrame}
            progress_callback: Optional callback(phase, current, total)

        Returns:
            Dictionary of {code: StockPredictions}
        """
        codes = list(data_dict.keys())
        logger.info(f"Starting inference for {len(codes)} stocks")

        # Initialize results
        for code, df in data_dict.items():
            self.results[code] = StockPredictions(
                code=code,
                current_price=get_current_price(df),
            )

        # Phase 1: Chronos
        if self.config.models.get("chronos") and self.config.models["chronos"].enabled:
            logger.info("=" * 50)
            logger.info("Phase 1: Chronos-Bolt Inference")
            logger.info("=" * 50)
            self._run_chronos_phase(data_dict)

        # Phase 2: TTM
        if self.config.models.get("ttm") and self.config.models["ttm"].enabled:
            logger.info("=" * 50)
            logger.info("Phase 2: TTM Inference")
            logger.info("=" * 50)
            self._run_ttm_phase(data_dict)

        # Phase 3: Moirai
        if self.config.models.get("moirai") and self.config.models["moirai"].enabled:
            logger.info("=" * 50)
            logger.info("Phase 3: Moirai Inference")
            logger.info("=" * 50)
            self._run_moirai_phase(data_dict)

        logger.info(f"Inference complete for {len(self.results)} stocks")
        return self.results

    def _run_chronos_phase(self, data_dict: dict[str, pd.DataFrame]) -> None:
        """Run Chronos inference for all stocks and horizons."""
        chronos_config = self.config.models["chronos"]

        wrapper = ChronosWrapper.from_config(chronos_config)
        if not wrapper.load():
            logger.error("Failed to load Chronos model")
            return

        try:
            for code, df in tqdm(data_dict.items(), desc="Chronos"):
                model_pred = ModelPredictions(model_name="Chronos")

                for horizon_name, horizon_cfg in self.config.horizons.items():
                    # Prepare input
                    input_data = prepare_model_input(
                        df,
                        context_length=horizon_cfg.context_length,
                        column="close",
                    )

                    # Run prediction
                    result = wrapper.predict(input_data, horizon_cfg.prediction_length)

                    if result.success and result.median is not None:
                        model_pred.horizons[horizon_name] = HorizonPrediction(
                            horizon=horizon_name,
                            prediction_length=horizon_cfg.prediction_length,
                            predicted_price=result.median,
                            current_price=self.results[code].current_price,
                        )
                    else:
                        model_pred.horizons[horizon_name] = HorizonPrediction(
                            horizon=horizon_name,
                            prediction_length=horizon_cfg.prediction_length,
                            predicted_price=None,
                            current_price=self.results[code].current_price,
                            success=False,
                            error=result.error,
                        )

                self.results[code].models["Chronos"] = model_pred

        finally:
            wrapper.unload()
            clear_memory()
            self._log_memory("Chronos unloaded")

    def _run_ttm_phase(self, data_dict: dict[str, pd.DataFrame]) -> None:
        """Run TTM inference with per-horizon model loading."""
        ttm_config = self.config.models["ttm"]

        manager = TTMHorizonManager(model_name=ttm_config.name)

        try:
            # Process each horizon separately (제12조 Phase 2)
            for horizon_name, horizon_cfg in self.config.horizons.items():
                logger.info(f"TTM - Processing horizon: {horizon_name}")

                # Get wrapper for this horizon
                wrapper = manager.get_wrapper(
                    context_length=horizon_cfg.context_length,
                    prediction_length=horizon_cfg.prediction_length,
                    horizon_name=horizon_name,
                )

                for code, df in tqdm(data_dict.items(), desc=f"TTM-{horizon_name}"):
                    # Initialize model predictions if needed
                    if "TTM" not in self.results[code].models:
                        self.results[code].models["TTM"] = ModelPredictions(model_name="TTM")

                    # Scale data for TTM (제9조)
                    scaler = StandardScaler()
                    scaled_df = scaler.fit_transform(df.copy(), columns=["close"])

                    # Prepare scaled input
                    input_data = prepare_model_input(
                        scaled_df,
                        context_length=horizon_cfg.context_length,
                        column="close",
                    )

                    # Run prediction
                    result = wrapper.predict(input_data, horizon_cfg.prediction_length)

                    if result.success and result.median is not None:
                        # Inverse transform the prediction
                        predicted_price = scaler.inverse_transform_value(result.median, "close")

                        self.results[code].models["TTM"].horizons[horizon_name] = HorizonPrediction(
                            horizon=horizon_name,
                            prediction_length=horizon_cfg.prediction_length,
                            predicted_price=predicted_price,
                            current_price=self.results[code].current_price,
                        )
                    else:
                        self.results[code].models["TTM"].horizons[horizon_name] = HorizonPrediction(
                            horizon=horizon_name,
                            prediction_length=horizon_cfg.prediction_length,
                            predicted_price=None,
                            current_price=self.results[code].current_price,
                            success=False,
                            error=result.error,
                        )

                # Memory cleanup between horizons
                self._log_memory(f"TTM {horizon_name} complete")

        finally:
            manager.unload()
            clear_memory()
            self._log_memory("TTM unloaded")

    def _run_moirai_phase(self, data_dict: dict[str, pd.DataFrame]) -> None:
        """Run Moirai inference for all stocks and horizons."""
        moirai_config = self.config.models["moirai"]

        wrapper = MoiraiWrapper.from_config(moirai_config)
        if not wrapper.load():
            logger.error("Failed to load Moirai model")
            return

        try:
            for code, df in tqdm(data_dict.items(), desc="Moirai"):
                model_pred = ModelPredictions(model_name="Moirai")

                for horizon_name, horizon_cfg in self.config.horizons.items():
                    # Prepare input
                    input_data = prepare_model_input(
                        df,
                        context_length=horizon_cfg.context_length,
                        column="close",
                    )

                    # Run prediction
                    result = wrapper.predict(
                        input_data,
                        prediction_length=horizon_cfg.prediction_length,
                        context_length=horizon_cfg.context_length,
                    )

                    if result.success and result.median is not None:
                        model_pred.horizons[horizon_name] = HorizonPrediction(
                            horizon=horizon_name,
                            prediction_length=horizon_cfg.prediction_length,
                            predicted_price=result.median,
                            current_price=self.results[code].current_price,
                        )
                    else:
                        model_pred.horizons[horizon_name] = HorizonPrediction(
                            horizon=horizon_name,
                            prediction_length=horizon_cfg.prediction_length,
                            predicted_price=None,
                            current_price=self.results[code].current_price,
                            success=False,
                            error=result.error,
                        )

                self.results[code].models["Moirai"] = model_pred

        finally:
            wrapper.unload()
            clear_memory()
            self._log_memory("Moirai unloaded")

    def _log_memory(self, message: str) -> None:
        """Log memory status."""
        info = get_memory_info()
        if info.cuda_available:
            logger.debug(
                f"{message} - GPU: {info.gpu_allocated:.2f}GB allocated, "
                f"{info.gpu_reserved:.2f}GB reserved"
            )


def run_single_stock_inference(
    config: Config,
    code: str,
    df: pd.DataFrame,
) -> StockPredictions:
    """Run inference for a single stock.

    Utility function for testing or single-stock prediction.

    Args:
        config: Configuration object
        code: Stock code
        df: Stock DataFrame

    Returns:
        StockPredictions for the stock
    """
    engine = InferenceEngine(config)
    results = engine.run_inference({code: df})
    return results.get(code)
