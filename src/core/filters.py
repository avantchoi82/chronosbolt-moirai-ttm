"""Filtering and tagging system for stock selection.

Implements CONSTITUTION.md 제20조~제24조.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from src.core.scorer import StockScore
    from src.utils.config_loader import FilterConfig

logger = logging.getLogger("ensemble")


# Investment type tags (제24조)
TAG_SHORT_SURGE = "Short-term Surge"  # 단기급등형
TAG_LONG_GROWTH = "Long-term Growth"  # 장기성장형
TAG_HIGH_CONFIDENCE = "High Confidence"  # 고확신형
TAG_BALANCED = "Balanced"  # 균형형
TAG_MIXED = "Mixed"  # 혼조형


@dataclass
class VolumeStats:
    """Volume statistics for a stock."""
    code: str
    avg_volume: float  # Average daily volume
    avg_value: float   # Average daily trading value
    days: int          # Number of days analyzed


def calculate_volume_stats(
    df: pd.DataFrame,
    code: str,
    days: int = 20,
) -> VolumeStats:
    """Calculate volume statistics for filtering (제22조).

    Args:
        df: OHLCV DataFrame
        code: Stock code
        days: Number of recent days to average

    Returns:
        VolumeStats object
    """
    recent = df.tail(days)

    avg_volume = float(recent["volume"].mean()) if "volume" in recent else 0.0
    avg_value = float((recent["close"] * recent["volume"]).mean()) if all(c in recent for c in ["close", "volume"]) else 0.0

    return VolumeStats(
        code=code,
        avg_volume=avg_volume,
        avg_value=avg_value,
        days=min(days, len(recent)),
    )


def filter_by_volume(
    scores: list[StockScore],
    volume_stats: dict[str, VolumeStats],
    min_volume: int = 50000,
) -> list[StockScore]:
    """Filter stocks by minimum average volume (제22조).

    Args:
        scores: List of StockScore
        volume_stats: Dictionary of {code: VolumeStats}
        min_volume: Minimum average daily volume (50,000 shares)

    Returns:
        Filtered list of StockScore
    """
    filtered = []
    excluded_count = 0

    for score in scores:
        stats = volume_stats.get(score.code)
        if stats and stats.avg_volume >= min_volume:
            filtered.append(score)
        else:
            excluded_count += 1
            logger.debug(
                f"Excluded {score.code} ({score.name}): "
                f"volume {stats.avg_volume:.0f} < {min_volume}" if stats else f"no volume data"
            )

    if excluded_count > 0:
        logger.info(f"Volume filter: excluded {excluded_count} stocks")

    return filtered


def filter_by_value(
    scores: list[StockScore],
    volume_stats: dict[str, VolumeStats],
    min_value: int = 500000000,
) -> list[StockScore]:
    """Filter stocks by minimum average trading value (제22조).

    Args:
        scores: List of StockScore
        volume_stats: Dictionary of {code: VolumeStats}
        min_value: Minimum average daily value (500 million KRW)

    Returns:
        Filtered list of StockScore
    """
    filtered = []
    excluded_count = 0

    for score in scores:
        stats = volume_stats.get(score.code)
        if stats and stats.avg_value >= min_value:
            filtered.append(score)
        else:
            excluded_count += 1
            logger.debug(
                f"Excluded {score.code} ({score.name}): "
                f"value {stats.avg_value/1e8:.1f}억 < {min_value/1e8:.1f}억" if stats else f"no value data"
            )

    if excluded_count > 0:
        logger.info(f"Value filter: excluded {excluded_count} stocks")

    return filtered


def filter_by_sector(
    scores: list[StockScore],
    sectors: dict[str, str],
    max_per_sector: int = 3,
) -> list[StockScore]:
    """Filter to limit stocks per sector (제22조).

    Args:
        scores: List of StockScore (should be pre-sorted by score)
        sectors: Dictionary of {code: sector}
        max_per_sector: Maximum stocks per sector (3)

    Returns:
        Filtered list with sector diversity
    """
    filtered = []
    sector_counts: dict[str, int] = {}
    excluded_count = 0

    for score in scores:
        sector = sectors.get(score.code, "Unknown")

        current_count = sector_counts.get(sector, 0)
        if current_count < max_per_sector:
            filtered.append(score)
            sector_counts[sector] = current_count + 1
        else:
            excluded_count += 1
            logger.debug(
                f"Excluded {score.code} ({score.name}): "
                f"sector {sector} already has {max_per_sector} stocks"
            )

    if excluded_count > 0:
        logger.info(f"Sector filter: excluded {excluded_count} stocks")

    return filtered


def select_top_n(
    scores: list[StockScore],
    top_n: int = 15,
) -> list[StockScore]:
    """Select top N stocks by score (제22조).

    Args:
        scores: List of StockScore (should be pre-sorted)
        top_n: Number to select (15)

    Returns:
        Top N stocks
    """
    return scores[:top_n]


def assign_tag(score: StockScore) -> str:
    """Assign investment type tag (제24조).

    Tags:
    - Short-term Surge: short > 5% AND short > long
    - Long-term Growth: long > 15% AND long > short × 1.5
    - High Confidence: agreement > 0.85
    - Balanced: short > 0 AND long > 0
    - Mixed: otherwise

    Args:
        score: StockScore object

    Returns:
        Tag string
    """
    short_ret = score.short_return * 100  # Convert to percentage
    long_ret = score.long_return * 100
    agreement = score.avg_agreement

    # Check conditions in order
    if short_ret > 5 and short_ret > long_ret:
        return TAG_SHORT_SURGE

    if long_ret > 15 and long_ret > short_ret * 1.5:
        return TAG_LONG_GROWTH

    if agreement > 0.85:
        return TAG_HIGH_CONFIDENCE

    if short_ret > 0 and long_ret > 0:
        return TAG_BALANCED

    return TAG_MIXED


def assign_tags(scores: list[StockScore]) -> list[StockScore]:
    """Assign tags to all stocks.

    Args:
        scores: List of StockScore

    Returns:
        Same list with tags assigned
    """
    for score in scores:
        score.tag = assign_tag(score)
    return scores


class FilterPipeline:
    """Pipeline for applying all filters sequentially."""

    def __init__(self, config: FilterConfig):
        """Initialize filter pipeline.

        Args:
            config: Filter configuration
        """
        self.config = config

    def apply_filters(
        self,
        scores: list[StockScore],
        volume_stats: dict[str, VolumeStats],
        sectors: dict[str, str] | None = None,
    ) -> list[StockScore]:
        """Apply all filters in sequence.

        Args:
            scores: List of StockScore (should be pre-sorted by final_score)
            volume_stats: Dictionary of {code: VolumeStats}
            sectors: Optional dictionary of {code: sector}

        Returns:
            Filtered and tagged list of StockScore
        """
        logger.info(f"Starting filter pipeline with {len(scores)} stocks")

        result = scores

        # Filter by volume (제22조)
        result = filter_by_volume(result, volume_stats, self.config.min_volume)
        logger.info(f"After volume filter: {len(result)} stocks")

        # Filter by value (제22조)
        result = filter_by_value(result, volume_stats, self.config.min_value)
        logger.info(f"After value filter: {len(result)} stocks")

        # Filter by sector diversity (제22조)
        if sectors:
            result = filter_by_sector(result, sectors, self.config.max_sector_count)
            logger.info(f"After sector filter: {len(result)} stocks")

        # Select top N (제22조)
        result = select_top_n(result, self.config.top_n)
        logger.info(f"After top-N selection: {len(result)} stocks")

        # Assign tags (제24조)
        result = assign_tags(result)

        return result


def get_sector_info(codes: list[str]) -> dict[str, str]:
    """Get sector information for stock codes.

    Args:
        codes: List of stock codes

    Returns:
        Dictionary of {code: sector}
    """
    sectors = {}

    try:
        from pykrx import stock

        for code in codes:
            try:
                # pykrx doesn't have direct sector info
                # This is a placeholder - in production, use KRX sector data
                sectors[code] = "Unknown"
            except Exception:
                sectors[code] = "Unknown"
    except ImportError:
        pass

    # Fallback: try FinanceDataReader
    if not sectors:
        try:
            import FinanceDataReader as fdr
            krx = fdr.StockListing("KRX")

            for code in codes:
                match = krx[krx["Code"] == code]
                if not match.empty and "Sector" in match.columns:
                    sectors[code] = match.iloc[0]["Sector"]
                else:
                    sectors[code] = "Unknown"
        except Exception:
            sectors = {code: "Unknown" for code in codes}

    return sectors


def calculate_all_volume_stats(
    data_dict: dict[str, pd.DataFrame],
    days: int = 20,
) -> dict[str, VolumeStats]:
    """Calculate volume stats for all stocks.

    Args:
        data_dict: Dictionary of {code: DataFrame}
        days: Number of days to average

    Returns:
        Dictionary of {code: VolumeStats}
    """
    stats = {}
    for code, df in data_dict.items():
        stats[code] = calculate_volume_stats(df, code, days)
    return stats
