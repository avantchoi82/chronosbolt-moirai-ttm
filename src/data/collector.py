"""Data collector with pykrx primary and FinanceDataReader fallback."""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from src.utils.config_loader import DataConfig

logger = logging.getLogger("ensemble")


@dataclass
class CollectionResult:
    """Result of data collection for a single stock."""
    code: str
    success: bool
    data: pd.DataFrame | None = None
    error: str | None = None
    source: str = ""


def _get_date_range(days: int) -> tuple[str, str]:
    """Get date range for data collection.

    Args:
        days: Number of days to collect

    Returns:
        Tuple of (start_date, end_date) in YYYYMMDD format
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days * 1.5)  # Extra buffer for non-trading days

    return start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")


def _collect_with_pykrx(code: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    """Collect OHLCV data using pykrx.

    Args:
        code: Stock code
        start_date: Start date (YYYYMMDD)
        end_date: End date (YYYYMMDD)

    Returns:
        DataFrame with OHLCV or None on failure
    """
    try:
        from pykrx import stock

        df = stock.get_market_ohlcv_by_date(start_date, end_date, code)

        if df.empty:
            return None

        # pykrx returns columns: 시가, 고가, 저가, 종가, 거래량, (등락률 - optional)
        # Normalize column names by mapping Korean to English
        column_map = {
            "시가": "open",
            "고가": "high",
            "저가": "low",
            "종가": "close",
            "거래량": "volume",
        }
        df = df.rename(columns=column_map)

        # Select only OHLCV columns (ignore 등락률 if present)
        required_cols = ["open", "high", "low", "close", "volume"]
        df = df[[col for col in required_cols if col in df.columns]]

        df.index.name = "date"
        df = df.reset_index()

        # Convert types
        df["date"] = pd.to_datetime(df["date"])
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").astype("int64")

        return df

    except Exception as e:
        logger.debug(f"pykrx failed for {code}: {e}")
        return None


def _collect_with_fdr(code: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    """Collect OHLCV data using FinanceDataReader.

    Args:
        code: Stock code
        start_date: Start date (YYYYMMDD)
        end_date: End date (YYYYMMDD)

    Returns:
        DataFrame with OHLCV or None on failure
    """
    try:
        import FinanceDataReader as fdr

        # FDR uses YYYY-MM-DD format
        start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"

        df = fdr.DataReader(code, start, end)

        if df.empty:
            return None

        # Normalize column names
        df = df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })

        df.index.name = "date"
        df = df.reset_index()
        df["date"] = pd.to_datetime(df["date"])

        # Select only OHLCV columns
        df = df[["date", "open", "high", "low", "close", "volume"]]

        return df

    except Exception as e:
        logger.debug(f"FDR failed for {code}: {e}")
        return None


class DataCache:
    """Simple file-based cache for collected data."""

    def __init__(self, cache_dir: str | Path, expiry_hours: int = 24):
        """Initialize cache.

        Args:
            cache_dir: Cache directory path
            expiry_hours: Cache expiry time in hours
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.expiry_hours = expiry_hours

    def _get_cache_path(self, code: str) -> Path:
        """Get cache file path for a stock code."""
        return self.cache_dir / f"{code}.pkl"

    def _get_meta_path(self, code: str) -> Path:
        """Get metadata file path for a stock code."""
        return self.cache_dir / f"{code}.meta"

    def get(self, code: str) -> pd.DataFrame | None:
        """Get cached data if valid.

        Args:
            code: Stock code

        Returns:
            Cached DataFrame or None
        """
        cache_path = self._get_cache_path(code)
        meta_path = self._get_meta_path(code)

        if not cache_path.exists() or not meta_path.exists():
            return None

        # Check expiry
        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)
            cached_time = datetime.fromisoformat(meta["timestamp"])
            if datetime.now() - cached_time > timedelta(hours=self.expiry_hours):
                return None

            with open(cache_path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None

    def set(self, code: str, data: pd.DataFrame) -> None:
        """Cache data for a stock code.

        Args:
            code: Stock code
            data: DataFrame to cache
        """
        try:
            cache_path = self._get_cache_path(code)
            meta_path = self._get_meta_path(code)

            with open(cache_path, "wb") as f:
                pickle.dump(data, f)

            with open(meta_path, "w") as f:
                json.dump({"timestamp": datetime.now().isoformat()}, f)
        except Exception as e:
            logger.debug(f"Cache write failed for {code}: {e}")

    def clear(self) -> None:
        """Clear all cached data."""
        for f in self.cache_dir.glob("*.pkl"):
            f.unlink()
        for f in self.cache_dir.glob("*.meta"):
            f.unlink()


class DataCollector:
    """Data collector with caching and parallel processing."""

    def __init__(
        self,
        config: DataConfig | None = None,
        cache_dir: str | Path = "cache",
    ):
        """Initialize collector.

        Args:
            config: Data configuration
            cache_dir: Cache directory path
        """
        self.config = config
        self.collection_days = config.collection_days if config else 150
        self.max_workers = config.max_workers if config else 8
        self.retry_count = config.retry_count if config else 3
        self.cache_expiry = config.cache_expiry_hours if config else 24

        self.cache = DataCache(cache_dir, self.cache_expiry)

    def _collect_single(
        self,
        code: str,
        start_date: str,
        end_date: str,
        use_cache: bool = True,
    ) -> CollectionResult:
        """Collect data for a single stock.

        Args:
            code: Stock code
            start_date: Start date
            end_date: End date
            use_cache: Whether to use cache

        Returns:
            CollectionResult
        """
        # Try cache first
        if use_cache:
            cached = self.cache.get(code)
            if cached is not None:
                return CollectionResult(
                    code=code,
                    success=True,
                    data=cached,
                    source="cache",
                )

        # Try pykrx first, then FDR
        for attempt in range(self.retry_count):
            # Try pykrx
            df = _collect_with_pykrx(code, start_date, end_date)
            if df is not None:
                if use_cache:
                    self.cache.set(code, df)
                return CollectionResult(
                    code=code,
                    success=True,
                    data=df,
                    source="pykrx",
                )

            # Fallback to FDR
            df = _collect_with_fdr(code, start_date, end_date)
            if df is not None:
                if use_cache:
                    self.cache.set(code, df)
                return CollectionResult(
                    code=code,
                    success=True,
                    data=df,
                    source="fdr",
                )

            # Rate limiting between retries
            if attempt < self.retry_count - 1:
                time.sleep(0.5)

        return CollectionResult(
            code=code,
            success=False,
            error="All collection methods failed",
        )

    def collect(
        self,
        codes: list[str],
        use_cache: bool = True,
        progress_callback: callable | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Collect data for multiple stocks in parallel.

        Args:
            codes: List of stock codes
            use_cache: Whether to use cache
            progress_callback: Optional callback(current, total, code)

        Returns:
            Dictionary of {code: DataFrame}
        """
        start_date, end_date = _get_date_range(self.collection_days)
        results: dict[str, pd.DataFrame] = {}
        failed: list[str] = []

        logger.info(f"Collecting data for {len(codes)} stocks...")
        logger.info(f"Date range: {start_date} ~ {end_date}")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._collect_single, code, start_date, end_date, use_cache
                ): code
                for code in codes
            }

            completed = 0
            for future in as_completed(futures):
                completed += 1
                result = future.result()

                if result.success and result.data is not None:
                    results[result.code] = result.data
                    if progress_callback:
                        progress_callback(completed, len(codes), result.code)
                else:
                    failed.append(result.code)
                    logger.debug(f"Failed to collect {result.code}: {result.error}")

        logger.info(f"Collection complete: {len(results)} success, {len(failed)} failed")
        return results

    def collect_single(self, code: str, use_cache: bool = True) -> pd.DataFrame | None:
        """Collect data for a single stock.

        Args:
            code: Stock code
            use_cache: Whether to use cache

        Returns:
            DataFrame or None
        """
        start_date, end_date = _get_date_range(self.collection_days)
        result = self._collect_single(code, start_date, end_date, use_cache)
        return result.data if result.success else None


def get_stock_name(code: str) -> str | None:
    """Get stock name for a code.

    Args:
        code: Stock code

    Returns:
        Stock name or None
    """
    try:
        from pykrx import stock
        return stock.get_market_ticker_name(code)
    except Exception:
        pass

    try:
        import FinanceDataReader as fdr
        krx = fdr.StockListing("KRX")
        match = krx[krx["Code"] == code]
        if not match.empty:
            return match.iloc[0]["Name"]
    except Exception:
        pass

    return None


def get_stock_names(codes: list[str]) -> dict[str, str]:
    """Get stock names for multiple codes.

    Args:
        codes: List of stock codes

    Returns:
        Dictionary of {code: name}
    """
    names = {}
    try:
        import FinanceDataReader as fdr
        krx = fdr.StockListing("KRX")
        for code in codes:
            match = krx[krx["Code"] == code]
            if not match.empty:
                names[code] = match.iloc[0]["Name"]
    except Exception:
        # Fallback to individual lookup
        for code in codes:
            name = get_stock_name(code)
            if name:
                names[code] = name

    return names
