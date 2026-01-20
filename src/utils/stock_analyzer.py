"""Stock Analyzer - Integrates news fetching and AI summarization.

Orchestrates the process of fetching news and generating AI summaries
for the top stocks from each source CSV. Uses parallel processing for speed.
Includes caching to limit API calls (7-day expiry per stock).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from .news_fetcher import fetch_stock_info, fetch_multiple_stocks, StockNews
from .ai_summarizer import generate_summary, StockSummary
from .summary_cache import (
    load_cache,
    save_cache,
    is_cache_valid,
    get_cached_summary,
    cache_summary,
    get_cache_stats,
)

logger = logging.getLogger("ensemble")

# Max parallel workers for AI summarization (keep low to avoid rate limits)
MAX_AI_WORKERS = 2

# Delay between API calls (seconds)
AI_DELAY = 1.0


def analyze_top_stocks(
    csv_path: Path,
    source: str,
    top_n: int = 10,
    enable_ai: bool = True,
) -> dict[str, StockSummary]:
    """Analyze top stocks from a CSV file using parallel processing.

    Args:
        csv_path: Path to source CSV file
        source: Source name (chartking, real, xgboost, lgbm)
        top_n: Number of top stocks to analyze
        enable_ai: Whether to enable AI summarization

    Returns:
        Dictionary of {stock_code: StockSummary}
    """
    if not csv_path or not csv_path.exists():
        logger.warning(f"CSV not found: {csv_path}")
        return {}

    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig", comment="#")
    except Exception as e:
        logger.error(f"Failed to read CSV {csv_path}: {e}")
        return {}

    # Determine code and name columns based on source
    code_col = None
    name_col = None

    if source in ["chartking", "real"]:
        code_col = "티커"
        name_col = "종목명"
    elif source in ["xgboost", "lgbm"]:
        code_col = "ticker"
        name_col = "name"

    if code_col not in df.columns or name_col not in df.columns:
        logger.warning(f"Required columns not found in {source} CSV")
        return {}

    # Collect stocks to process
    stocks_to_process = []
    for _, row in df.head(top_n).iterrows():
        code = str(row.get(code_col, "")).split(".")[0].zfill(6)
        name = str(row.get(name_col, ""))
        if code and name:
            stocks_to_process.append((code, name))

    if not stocks_to_process:
        return {}

    logger.info(f"Fetching news for {len(stocks_to_process)} stocks in parallel...")

    # Step 1: Parallel fetch news for all stocks
    stock_infos = fetch_multiple_stocks(stocks_to_process)

    # Create mapping from code to StockNews
    info_map = {info.code: info for info in stock_infos}

    summaries = {}

    if not enable_ai:
        # Without AI, just create basic summaries
        for code, name in stocks_to_process:
            info = info_map.get(code)
            summaries[code] = StockSummary(
                code=code,
                name=name,
                summary="AI 요약 비활성화",
                keywords=[],
                target_prices=info.target_prices if info else [],
            )
        return summaries

    # Load cache
    cache = load_cache()
    cache_stats = get_cache_stats(cache)
    logger.info(f"Cache loaded: {cache_stats['valid']} valid, {cache_stats['expired']} expired")

    # Step 2: Generate AI summaries (with caching)
    cached_count = 0
    new_count = 0

    for idx, info in enumerate(stock_infos):
        try:
            # Check cache first
            cached = get_cached_summary(info.code, cache)
            if cached:
                # Use cached summary
                summaries[info.code] = StockSummary(
                    code=cached["code"],
                    name=cached["name"],
                    summary=cached["summary"],
                    keywords=cached.get("keywords", []),
                    target_prices=cached.get("target_prices", []),
                )
                cached_count += 1
                logger.info(f"  [{idx+1}/{len(stock_infos)}] 📦 {info.name}: (캐시 사용)")
                continue

            # Generate new summary
            if info.news_titles:
                summary = generate_summary(info)
            else:
                summary = StockSummary(
                    code=info.code,
                    name=info.name,
                    summary="뉴스 정보가 부족합니다.",
                    keywords=[],
                    target_prices=info.target_prices,
                )

            summaries[info.code] = summary
            new_count += 1

            # Cache the new summary
            cache_summary(
                info.code,
                {
                    "code": summary.code,
                    "name": summary.name,
                    "summary": summary.summary,
                    "keywords": summary.keywords,
                    "target_prices": summary.target_prices,
                },
                cache,
            )

            logger.info(f"  [{idx+1}/{len(stock_infos)}] ✓ {summary.name}: {summary.summary[:30]}...")

            # Delay between API calls to avoid rate limits
            if idx < len(stock_infos) - 1 and new_count > 0:
                time.sleep(AI_DELAY)

        except Exception as e:
            logger.error(f"AI summary error for {info.name}: {e}")

    # Save cache
    save_cache(cache)
    logger.info(f"Summary stats: {new_count} new (API), {cached_count} cached")

    return summaries


def analyze_all_sources(
    source_csvs: dict[str, Path] | None = None,
    xgboost_csv: Path | None = None,
    lgbm_csv: Path | None = None,
    top_n: int = 10,
    enable_ai: bool = True,
) -> dict[str, dict[str, StockSummary]]:
    """Analyze top stocks from all source CSVs.

    Args:
        source_csvs: Dictionary of {source_name: csv_path} for chartking, real
        xgboost_csv: Path to XGBoost CSV
        lgbm_csv: Path to LGBM CSV
        top_n: Number of top stocks per source
        enable_ai: Whether to enable AI summarization

    Returns:
        Nested dictionary: {source_name: {stock_code: StockSummary}}
    """
    all_summaries = {}

    # Analyze chartking and real
    if source_csvs:
        for source, csv_path in source_csvs.items():
            if csv_path and csv_path.exists():
                logger.info(f"\n=== Analyzing {source} ===")
                all_summaries[source] = analyze_top_stocks(
                    csv_path, source, top_n, enable_ai
                )

    # Analyze XGBoost
    if xgboost_csv and xgboost_csv.exists():
        logger.info(f"\n=== Analyzing xgboost ===")
        all_summaries["xgboost"] = analyze_top_stocks(
            xgboost_csv, "xgboost", top_n, enable_ai
        )

    # Analyze LGBM (in ML tab, skip for stocks tab)
    # LGBM is shown in a separate tab, so we can skip it here
    # or analyze it separately if needed

    return all_summaries


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)

    # Test with a sample stock
    from .news_fetcher import fetch_stock_info
    from .ai_summarizer import generate_summary

    info = fetch_stock_info("005930", "삼성전자")
    print(f"News: {len(info.news_titles)}")
    print(f"Target prices: {info.target_prices}")

    if info.news_titles:
        summary = generate_summary(info)
        print(f"\nSummary: {summary.summary}")
        print(f"Keywords: {summary.keywords}")
