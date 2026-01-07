"""Scoring system for ensemble stock ranking.

Implements CONSTITUTION.md 제14조~제19조.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from src.core.inference import StockPredictions
    from src.utils.config_loader import Config, ScoringConfig

logger = logging.getLogger("ensemble")


@dataclass
class HorizonScore:
    """Score for a single horizon."""
    horizon: str
    raw_return: float  # Raw return percentage
    capped_return: float  # After cap applied
    daily_return: float  # Normalized to daily
    model_returns: dict[str, float] = field(default_factory=dict)  # Per-model returns
    agreement: float = 0.0  # Model agreement score


@dataclass
class StockScore:
    """Complete score for a single stock."""
    code: str
    name: str
    current_price: float

    # Per-horizon scores
    horizons: dict[str, HorizonScore] = field(default_factory=dict)

    # Ensemble returns (weighted by model)
    short_return: float = 0.0
    mid_return: float = 0.0
    long_return: float = 0.0

    # Final scores
    weighted_daily_return: float = 0.0
    avg_agreement: float = 0.0
    freq_count: int = 1
    freq_bonus: float = 0.0
    final_score: float = 0.0

    # Tag
    tag: str = ""


def calc_raw_return(predicted_price: float, current_price: float) -> float:
    """Calculate raw return percentage (제14조).

    Args:
        predicted_price: Model's predicted price
        current_price: Current stock price

    Returns:
        Raw return as decimal (e.g., 0.05 for 5%)
    """
    if current_price <= 0:
        return 0.0
    return (predicted_price - current_price) / current_price


def cap_return(raw_return: float, cap: float) -> float:
    """Apply return cap (제16조).

    Args:
        raw_return: Raw return decimal
        cap: Maximum absolute return (e.g., 0.30 for ±30%)

    Returns:
        Capped return
    """
    return max(-cap, min(cap, raw_return))


def normalize_return(capped_return: float, prediction_days: int) -> float:
    """Normalize return to daily basis (제17조).

    Args:
        capped_return: Capped return decimal
        prediction_days: Number of prediction days

    Returns:
        Daily normalized return
    """
    if prediction_days <= 0:
        return 0.0
    return capped_return / prediction_days


def calc_direction_agreement(returns: list[float]) -> float:
    """Calculate direction agreement among model returns (제18조).

    Args:
        returns: List of returns from different models

    Returns:
        Agreement score 0-1 (1 = all same direction)
    """
    if not returns:
        return 0.0

    valid_returns = [r for r in returns if r is not None]
    if len(valid_returns) < 2:
        return 1.0  # Single model always agrees with itself

    # Count positive, negative, zero
    positive = sum(1 for r in valid_returns if r > 0)
    negative = sum(1 for r in valid_returns if r < 0)
    total = len(valid_returns)

    # Agreement is the proportion of the majority direction
    majority = max(positive, negative, total - positive - negative)
    return majority / total


def calc_magnitude_agreement(returns: list[float]) -> float:
    """Calculate magnitude agreement using coefficient of variation (제18조).

    Args:
        returns: List of returns from different models

    Returns:
        Agreement score 0-1 (1 = low variation)
    """
    valid_returns = [r for r in returns if r is not None]
    if len(valid_returns) < 2:
        return 1.0

    mean_abs = np.mean(np.abs(valid_returns))
    if mean_abs < 1e-6:
        return 1.0  # All near zero

    std = np.std(valid_returns)
    cv = std / mean_abs  # Coefficient of variation

    # Convert CV to agreement (lower CV = higher agreement)
    # CV of 0 -> agreement 1, CV of 2+ -> agreement 0
    agreement = max(0, 1 - cv / 2)
    return agreement


def calc_agreement(
    returns: list[float],
    direction_weight: float = 0.60,
    magnitude_weight: float = 0.40,
) -> float:
    """Calculate overall model agreement (제18조).

    Args:
        returns: List of returns from different models
        direction_weight: Weight for direction agreement (60%)
        magnitude_weight: Weight for magnitude agreement (40%)

    Returns:
        Overall agreement score 0-1
    """
    direction = calc_direction_agreement(returns)
    magnitude = calc_magnitude_agreement(returns)

    return direction * direction_weight + magnitude * magnitude_weight


def calc_freq_bonus(freq_count: int, factor: float = 0.02) -> float:
    """Calculate frequency bonus (제19조).

    Args:
        freq_count: Number of times stock was recommended
        factor: Bonus factor (0.02)

    Returns:
        Frequency bonus
    """
    if freq_count <= 1:
        return 0.0
    return math.log(1 + freq_count) * factor


def calc_final_score(
    weighted_daily_return: float,
    avg_agreement: float,
    freq_bonus: float,
    return_weight: float = 0.70,
    agreement_weight: float = 0.30,
) -> float:
    """Calculate final score (제19조).

    Formula:
        final = weighted_daily_return × (return_weight + agreement_weight × avg_agreement) + freq_bonus

    Args:
        weighted_daily_return: Time-weighted daily return
        avg_agreement: Average model agreement
        freq_bonus: Frequency bonus
        return_weight: Base return weight (0.70)
        agreement_weight: Agreement contribution (0.30)

    Returns:
        Final score
    """
    return weighted_daily_return * (return_weight + agreement_weight * avg_agreement) + freq_bonus


def ensemble_returns(
    model_returns: dict[str, float],
    model_weights: dict[str, float],
) -> float:
    """Calculate weighted ensemble return from multiple models (제6조).

    Args:
        model_returns: Dictionary of {model_name: return}
        model_weights: Dictionary of {model_name: weight}

    Returns:
        Weighted ensemble return
    """
    # Normalize model_weights keys to match model_returns (case-insensitive)
    weights_lower = {k.lower(): v for k, v in model_weights.items()}

    valid_returns = {}
    for model, ret in model_returns.items():
        model_lower = model.lower()
        if ret is not None and model_lower in weights_lower:
            valid_returns[model_lower] = (ret, weights_lower[model_lower])

    if not valid_returns:
        return 0.0

    # Normalize weights for available models
    total_weight = sum(w for _, w in valid_returns.values())
    if total_weight <= 0:
        return 0.0

    weighted_sum = sum(
        ret * (w / total_weight)
        for ret, w in valid_returns.values()
    )
    return weighted_sum


class Scorer:
    """Scorer for ensemble stock ranking."""

    def __init__(self, config: Config):
        """Initialize scorer.

        Args:
            config: Configuration object
        """
        self.config = config
        self.scoring_cfg = config.scoring
        self.model_weights = config.get_model_weights()
        self.horizon_weights = config.get_horizon_weights()

    def score_stock(
        self,
        code: str,
        name: str,
        predictions: StockPredictions,
        freq_count: int = 1,
    ) -> StockScore:
        """Calculate complete score for a stock.

        Args:
            code: Stock code
            name: Stock name
            predictions: Model predictions
            freq_count: Recommendation frequency

        Returns:
            StockScore with all calculated metrics
        """
        score = StockScore(
            code=code,
            name=name,
            current_price=predictions.current_price,
            freq_count=freq_count,
        )

        # Calculate per-horizon scores
        horizon_daily_returns = {}

        for horizon_name, horizon_cfg in self.config.horizons.items():
            # Collect returns from all models
            model_returns = {}

            for model_name in ["Chronos", "TTM", "Moirai"]:
                if model_name in predictions.models:
                    model_pred = predictions.models[model_name]
                    if horizon_name in model_pred.horizons:
                        hp = model_pred.horizons[horizon_name]
                        if hp.predicted_price is not None:
                            ret = calc_raw_return(hp.predicted_price, predictions.current_price)
                            model_returns[model_name] = ret

            if not model_returns:
                continue

            # Ensemble the returns (weighted by model)
            ensemble_ret = ensemble_returns(model_returns, self.model_weights)

            # Apply cap (제16조)
            capped_ret = cap_return(ensemble_ret, horizon_cfg.return_cap)

            # Normalize to daily (제17조)
            daily_ret = normalize_return(capped_ret, horizon_cfg.prediction_length)

            # Calculate agreement (제18조)
            returns_list = list(model_returns.values())
            agreement = calc_agreement(
                returns_list,
                self.scoring_cfg.direction_weight,
                self.scoring_cfg.magnitude_weight,
            )

            # Store horizon score
            horizon_score = HorizonScore(
                horizon=horizon_name,
                raw_return=ensemble_ret,
                capped_return=capped_ret,
                daily_return=daily_ret,
                model_returns=model_returns,
                agreement=agreement,
            )
            score.horizons[horizon_name] = horizon_score
            horizon_daily_returns[horizon_name] = daily_ret

        # Store named returns
        if "short" in score.horizons:
            score.short_return = score.horizons["short"].capped_return
        if "mid" in score.horizons:
            score.mid_return = score.horizons["mid"].capped_return
        if "long" in score.horizons:
            score.long_return = score.horizons["long"].capped_return

        # Calculate weighted daily return (제19조)
        weighted_daily = 0.0
        for horizon_name, daily_ret in horizon_daily_returns.items():
            weight = self.horizon_weights.get(horizon_name, 0)
            weighted_daily += daily_ret * weight
        score.weighted_daily_return = weighted_daily

        # Calculate average agreement
        agreements = [h.agreement for h in score.horizons.values()]
        score.avg_agreement = np.mean(agreements) if agreements else 0.0

        # Calculate frequency bonus (제19조)
        score.freq_bonus = calc_freq_bonus(freq_count, self.scoring_cfg.freq_bonus_factor)

        # Calculate final score (제19조)
        score.final_score = calc_final_score(
            score.weighted_daily_return,
            score.avg_agreement,
            score.freq_bonus,
            self.scoring_cfg.return_weight,
            self.scoring_cfg.agreement_weight,
        )

        return score

    def score_all(
        self,
        predictions: dict[str, StockPredictions],
        names: dict[str, str],
        freq_counts: dict[str, int],
    ) -> dict[str, StockScore]:
        """Score all stocks.

        Args:
            predictions: Dictionary of {code: StockPredictions}
            names: Dictionary of {code: name}
            freq_counts: Dictionary of {code: frequency}

        Returns:
            Dictionary of {code: StockScore}
        """
        scores = {}

        for code, pred in predictions.items():
            name = names.get(code, code)
            freq = freq_counts.get(code, 1)
            scores[code] = self.score_stock(code, name, pred, freq)

        logger.info(f"Scored {len(scores)} stocks")
        return scores

    def rank_stocks(
        self,
        scores: dict[str, StockScore],
        top_n: int | None = None,
    ) -> list[StockScore]:
        """Rank stocks by final score.

        Args:
            scores: Dictionary of {code: StockScore}
            top_n: Maximum number to return (None for all)

        Returns:
            List of StockScore sorted by final_score descending
        """
        ranked = sorted(
            scores.values(),
            key=lambda s: s.final_score,
            reverse=True,
        )

        if top_n:
            ranked = ranked[:top_n]

        return ranked
