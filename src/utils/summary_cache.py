"""AI Summary Cache - Stores summaries to limit API calls.

Caches AI summaries per stock with 7-day expiration to reduce API costs.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import asdict

logger = logging.getLogger("ensemble")

# Cache settings
CACHE_FILE = Path(__file__).parent.parent.parent / "data" / "summary_cache.json"
CACHE_EXPIRY_DAYS = 7


def _ensure_cache_dir():
    """Ensure cache directory exists."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_cache() -> dict:
    """Load cache from file.

    Returns:
        Dictionary of {stock_code: {summary_data, cached_at}}
    """
    _ensure_cache_dir()

    if not CACHE_FILE.exists():
        return {}

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load cache: {e}")
        return {}


def save_cache(cache: dict) -> None:
    """Save cache to file.

    Args:
        cache: Cache dictionary to save
    """
    _ensure_cache_dir()

    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save cache: {e}")


def is_cache_valid(stock_code: str, cache: dict) -> bool:
    """Check if cached summary is still valid (less than 7 days old).

    Args:
        stock_code: Stock code to check
        cache: Cache dictionary

    Returns:
        True if cache is valid, False otherwise
    """
    if stock_code not in cache:
        return False

    cached_at = cache[stock_code].get("cached_at")
    if not cached_at:
        return False

    try:
        cached_date = datetime.fromisoformat(cached_at)
        expiry_date = cached_date + timedelta(days=CACHE_EXPIRY_DAYS)
        return datetime.now() < expiry_date
    except Exception:
        return False


def get_cached_summary(stock_code: str, cache: dict) -> dict | None:
    """Get cached summary if valid.

    Args:
        stock_code: Stock code
        cache: Cache dictionary

    Returns:
        Cached summary data or None
    """
    if is_cache_valid(stock_code, cache):
        data = cache[stock_code].copy()
        data.pop("cached_at", None)
        return data
    return None


def cache_summary(stock_code: str, summary_data: dict, cache: dict) -> None:
    """Cache a summary.

    Args:
        stock_code: Stock code
        summary_data: Summary data to cache
        cache: Cache dictionary (will be modified)
    """
    cache[stock_code] = {
        **summary_data,
        "cached_at": datetime.now().isoformat(),
    }


def get_cache_stats(cache: dict) -> dict:
    """Get cache statistics.

    Args:
        cache: Cache dictionary

    Returns:
        Statistics dictionary
    """
    total = len(cache)
    valid = sum(1 for code in cache if is_cache_valid(code, cache))
    expired = total - valid

    return {
        "total": total,
        "valid": valid,
        "expired": expired,
    }
