"""Candidate pool management for stock screening."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from src.utils.config_loader import FilterConfig

logger = logging.getLogger("ensemble")

# Common column names for stock codes
CODE_COLUMN_PATTERNS = [
    r"^code$",
    r"^ticker$",
    r"^symbol$",
    r"^종목코드$",
    r"^stock_code$",
    r"^stockcode$",
    r".*code.*",
    r".*ticker.*",
]

# Patterns for ETF/ETN/SPAC/REITS detection
ETF_PATTERNS = [
    r"ETF$",
    r"^KODEX",
    r"^TIGER",
    r"^KBSTAR",
    r"^HANARO",
    r"^ARIRANG",
    r"^KOSEF",
    r"^KINDEX",
    r"^SOL",
    r"^ACE",
]

ETN_PATTERNS = [
    r"ETN$",
    r"^QV",
    r"^TRUE",
]

SPAC_PATTERNS = [
    r"스팩$",
    r"SPAC$",
    r"기업인수목적",
]

REITS_PATTERNS = [
    r"리츠$",
    r"REIT",
    r"부동산투자",
]


def _detect_code_column(df: pd.DataFrame) -> str | None:
    """Detect stock code column in DataFrame.

    Args:
        df: DataFrame to search

    Returns:
        Column name or None if not found
    """
    columns_lower = {col.lower(): col for col in df.columns}

    for pattern in CODE_COLUMN_PATTERNS:
        for col_lower, col_original in columns_lower.items():
            if re.match(pattern, col_lower, re.IGNORECASE):
                return col_original
    return None


def _normalize_code(code: str) -> str:
    """Normalize stock code to 6-digit format.

    Args:
        code: Raw stock code

    Returns:
        Normalized 6-digit code
    """
    # Remove any non-alphanumeric characters
    code = re.sub(r"[^0-9A-Za-z]", "", str(code))

    # If numeric, pad to 6 digits
    if code.isdigit():
        return code.zfill(6)

    return code


def _is_valid_korean_code(code: str) -> bool:
    """Check if code is a valid Korean stock code.

    Args:
        code: Stock code to validate

    Returns:
        True if valid
    """
    if not code or len(code) != 6:
        return False
    return code.isdigit()


def _matches_patterns(name: str, patterns: list[str]) -> bool:
    """Check if name matches any pattern.

    Args:
        name: Stock name to check
        patterns: List of regex patterns

    Returns:
        True if matches any pattern
    """
    for pattern in patterns:
        if re.search(pattern, name, re.IGNORECASE):
            return True
    return False


def load_candidates_from_csv(
    csv_paths: list[str | Path],
    exclude_etf: bool = True,
    exclude_etn: bool = True,
    exclude_spac: bool = True,
    exclude_reits: bool = True,
) -> dict[str, int]:
    """Load candidate stocks from multiple CSV files.

    Args:
        csv_paths: List of CSV file paths
        exclude_etf: Exclude ETF
        exclude_etn: Exclude ETN
        exclude_spac: Exclude SPAC
        exclude_reits: Exclude REITS

    Returns:
        Dictionary of {code: frequency}
    """
    candidates: dict[str, int] = {}
    name_mapping: dict[str, str] = {}  # code -> name for filtering

    for csv_path in csv_paths:
        csv_path = Path(csv_path)

        if not csv_path.exists():
            logger.warning(f"CSV file not found: {csv_path}")
            continue

        try:
            df = pd.read_csv(csv_path, dtype=str)
        except Exception as e:
            logger.warning(f"Failed to read CSV {csv_path}: {e}")
            continue

        # Detect code column
        code_col = _detect_code_column(df)
        if code_col is None:
            logger.warning(f"No code column found in {csv_path}")
            continue

        # Try to find name column for filtering
        name_col = None
        for col in df.columns:
            if any(n in col.lower() for n in ["name", "종목명", "종목", "이름"]):
                name_col = col
                break

        # Process each row
        for _, row in df.iterrows():
            raw_code = row[code_col]
            if pd.isna(raw_code):
                continue

            code = _normalize_code(raw_code)

            if not _is_valid_korean_code(code):
                continue

            # Get name if available
            if name_col and not pd.isna(row.get(name_col)):
                name = str(row[name_col])
                name_mapping[code] = name

            # Count frequency
            candidates[code] = candidates.get(code, 0) + 1

        logger.info(f"Loaded {len(df)} rows from {csv_path.name}")

    # Apply exclusion filters based on names
    if any([exclude_etf, exclude_etn, exclude_spac, exclude_reits]):
        filtered_candidates = {}
        excluded_count = 0

        for code, freq in candidates.items():
            name = name_mapping.get(code, "")

            should_exclude = False
            if exclude_etf and _matches_patterns(name, ETF_PATTERNS):
                should_exclude = True
            elif exclude_etn and _matches_patterns(name, ETN_PATTERNS):
                should_exclude = True
            elif exclude_spac and _matches_patterns(name, SPAC_PATTERNS):
                should_exclude = True
            elif exclude_reits and _matches_patterns(name, REITS_PATTERNS):
                should_exclude = True

            if should_exclude:
                excluded_count += 1
                logger.debug(f"Excluded: {code} ({name})")
            else:
                filtered_candidates[code] = freq

        logger.info(f"Excluded {excluded_count} ETF/ETN/SPAC/REITS")
        candidates = filtered_candidates

    logger.info(f"Total unique candidates: {len(candidates)}")
    return candidates


def get_top_candidates(
    candidates: dict[str, int],
    top_n: int | None = None,
    min_frequency: int = 1,
) -> list[tuple[str, int]]:
    """Get top candidates sorted by frequency.

    Args:
        candidates: Dictionary of {code: frequency}
        top_n: Maximum number to return (None for all)
        min_frequency: Minimum frequency threshold

    Returns:
        List of (code, frequency) tuples sorted by frequency desc
    """
    # Filter by minimum frequency
    filtered = [(code, freq) for code, freq in candidates.items() if freq >= min_frequency]

    # Sort by frequency descending
    sorted_candidates = sorted(filtered, key=lambda x: x[1], reverse=True)

    # Limit to top_n
    if top_n:
        sorted_candidates = sorted_candidates[:top_n]

    return sorted_candidates


class CandidatePool:
    """Manager for candidate stock pool."""

    def __init__(self, filter_config: FilterConfig | None = None):
        """Initialize candidate pool.

        Args:
            filter_config: Filter configuration
        """
        self.filter_config = filter_config
        self.candidates: dict[str, int] = {}
        self.loaded_files: list[str] = []

    def load_from_csvs(self, csv_paths: list[str | Path]) -> int:
        """Load candidates from CSV files.

        Args:
            csv_paths: List of CSV file paths

        Returns:
            Number of unique candidates loaded
        """
        exclude_etf = self.filter_config.exclude_etf if self.filter_config else True
        exclude_etn = self.filter_config.exclude_etn if self.filter_config else True
        exclude_spac = self.filter_config.exclude_spac if self.filter_config else True
        exclude_reits = self.filter_config.exclude_reits if self.filter_config else True

        self.candidates = load_candidates_from_csv(
            csv_paths=csv_paths,
            exclude_etf=exclude_etf,
            exclude_etn=exclude_etn,
            exclude_spac=exclude_spac,
            exclude_reits=exclude_reits,
        )

        self.loaded_files = [str(p) for p in csv_paths]
        return len(self.candidates)

    def add_code(self, code: str) -> None:
        """Add a single stock code.

        Args:
            code: Stock code to add
        """
        code = _normalize_code(code)
        if _is_valid_korean_code(code):
            self.candidates[code] = self.candidates.get(code, 0) + 1

    def get_codes(self) -> list[str]:
        """Get all candidate codes.

        Returns:
            List of stock codes
        """
        return list(self.candidates.keys())

    def get_frequency(self, code: str) -> int:
        """Get frequency for a code.

        Args:
            code: Stock code

        Returns:
            Frequency count
        """
        return self.candidates.get(_normalize_code(code), 0)

    def __len__(self) -> int:
        return len(self.candidates)

    def __contains__(self, code: str) -> bool:
        return _normalize_code(code) in self.candidates
