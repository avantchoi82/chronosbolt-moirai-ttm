"""Main entry point for ensemble stock scanner with multi-source aggregation.

Reads CSV files from 3 project directories:
- probability: stock_prob_engine/output
- chartking: output
- real: output
  ***깃허브 올리기 ->>  python main.py --push

Finds files starting with 'top30', gets latest file per day for 10 days,
and runs ensemble scoring.
"""

from __future__ import annotations

import re
import logging
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

import pandas as pd
import FinanceDataReader as fdr

from src.utils.config_loader import load_config
from src.data.collector import DataCollector
from src.core.inference import InferenceEngine, StockPredictions
from src.core.scorer import Scorer
from src.core.filters import assign_tag
from src.utils.reporter import Reporter
from src.utils.html_generator import generate_html_pages
from src.utils.github_publisher import publish_to_github_pages
import shutil

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ensemble.main")

# Source directories configuration
SOURCE_DIRS = {
    "probability": Path(r"C:\Users\user\PycharmProjects\probability\stock_prob_engine\output"),
    "chartking": Path(r"C:\Users\user\PycharmProjects\chartking\output"),
    "real": Path(r"C:\Users\user\PycharmProjects\real\output"),
}

# Column mappings for each source
COLUMN_MAPS = {
    "probability": {
        "code_col": "code",
        "name_col": "name",
        "price_col": "close",
    },
    "chartking": {
        "code_col": "티커",
        "name_col": "종목명",
        "price_col": "현재가",
    },
    "real": {
        "code_col": "티커",
        "name_col": "종목명",
        "price_col": "현재가",
    },
}


def parse_date_from_filename(filename: str) -> tuple[str, str] | None:
    """Extract date and time from filename.

    Handles patterns like:
    - top30_2026_01_07_1200.csv
    - top30_x1_2026_01_07_0953.csv

    Returns:
        Tuple of (date_str YYYY-MM-DD, time_str HHMM) or None if no match
    """
    # Pattern: top30[_x1]_YYYY_MM_DD_HHMM.csv
    pattern = r"top30(?:_x\d+)?_(\d{4})_(\d{2})_(\d{2})_(\d{4})\.csv"
    match = re.search(pattern, filename)

    if match:
        year, month, day, time = match.groups()
        date_str = f"{year}-{month}-{day}"
        return date_str, time
    return None


def get_latest_files_per_day(directory: Path, days: int = 10) -> list[Path]:
    """Get the latest file per day for the specified number of days.

    Args:
        directory: Directory to search
        days: Number of days to look back

    Returns:
        List of file paths (latest per day)
    """
    if not directory.exists():
        logger.warning(f"Directory not found: {directory}")
        return []

    # Find all top30 CSV files
    files = list(directory.glob("top30*.csv"))

    # Group files by date
    date_files: dict[str, list[tuple[str, Path]]] = defaultdict(list)

    for f in files:
        parsed = parse_date_from_filename(f.name)
        if parsed:
            date_str, time_str = parsed
            date_files[date_str].append((time_str, f))

    # Sort dates and take last N days
    sorted_dates = sorted(date_files.keys(), reverse=True)[:days]

    # Get latest file for each date
    result = []
    for date_str in sorted_dates:
        files_for_date = date_files[date_str]
        # Sort by time and take latest
        files_for_date.sort(key=lambda x: x[0], reverse=True)
        latest_file = files_for_date[0][1]
        result.append(latest_file)
        logger.info(f"  {date_str}: {latest_file.name}")

    return result


def normalize_code(code: str) -> str:
    """Normalize stock code to 6-digit format.

    Handles:
    - "000660" -> "000660"
    - "000660.KS" -> "000660"
    - "034020.KQ" -> "034020"
    - 660 -> "000660"
    """
    # Remove .KS, .KQ suffix
    code_str = str(code).split(".")[0]

    # Remove any non-digit characters
    code_str = re.sub(r"\D", "", code_str)

    # Pad to 6 digits
    return code_str.zfill(6)


def load_stocks_from_csv(filepath: Path, source: str) -> list[dict]:
    """Load stock list from CSV file.

    Args:
        filepath: Path to CSV file
        source: Source name (probability, chartking, real)

    Returns:
        List of dicts with code, name
    """
    col_map = COLUMN_MAPS.get(source, {})
    code_col = col_map.get("code_col", "code")
    name_col = col_map.get("name_col", "name")

    try:
        df = pd.read_csv(filepath, encoding="utf-8-sig")
    except Exception as e:
        logger.error(f"Failed to read {filepath}: {e}")
        return []

    if code_col not in df.columns:
        logger.warning(f"Column '{code_col}' not found in {filepath}")
        return []

    stocks = []
    for _, row in df.iterrows():
        code = normalize_code(row[code_col])
        name = row.get(name_col, code) if name_col in df.columns else code
        stocks.append({"code": code, "name": str(name)})

    return stocks


def get_market_caps(codes: list[str]) -> dict[str, float]:
    """Get market cap for stock codes using FinanceDataReader.

    Args:
        codes: List of stock codes

    Returns:
        Dictionary of {code: market_cap_in_억원}
    """
    market_caps = {}

    try:
        # Get KRX stock listing
        krx_stocks = fdr.StockListing("KRX")

        # Create code to market cap mapping
        # FinanceDataReader returns market cap in KRW
        for _, row in krx_stocks.iterrows():
            code = str(row.get("Code", "")).zfill(6)
            marcap = row.get("Marcap", 0)  # Market cap in KRW
            if code in codes and marcap:
                # Convert to 억원 (100 million KRW)
                market_caps[code] = marcap / 100_000_000

        logger.info(f"Market cap data retrieved for {len(market_caps)}/{len(codes)} stocks")

    except Exception as e:
        logger.error(f"Failed to get market cap data: {e}")

    return market_caps


def filter_by_market_cap(
    codes: list[str],
    min_market_cap: float = 1000,  # 1000억원
) -> list[str]:
    """Filter stocks by minimum market cap.

    Args:
        codes: List of stock codes
        min_market_cap: Minimum market cap in 억원 (default: 1000억)

    Returns:
        Filtered list of codes
    """
    market_caps = get_market_caps(codes)

    filtered = []
    excluded = []

    for code in codes:
        cap = market_caps.get(code, 0)
        if cap >= min_market_cap:
            filtered.append(code)
        else:
            excluded.append((code, cap))

    if excluded:
        logger.info(f"Excluded {len(excluded)} stocks with market cap < {min_market_cap}억원")
        for code, cap in excluded[:5]:  # Show first 5
            logger.debug(f"  {code}: {cap:.0f}억원")
        if len(excluded) > 5:
            logger.debug(f"  ... and {len(excluded) - 5} more")

    return filtered


def get_kospi_data(collection_days: int = 600) -> pd.DataFrame | None:
    """Get KOSPI index data for market prediction.

    Args:
        collection_days: Number of days to collect

    Returns:
        DataFrame with KOSPI data or None if failed
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=collection_days)

        # Get KOSPI index data using FinanceDataReader
        kospi = fdr.DataReader(
            "KS11",  # KOSPI index symbol
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )

        if kospi.empty:
            logger.warning("Failed to get KOSPI data")
            return None

        # Rename columns to lowercase for consistency
        kospi.columns = [c.lower() for c in kospi.columns]

        logger.info(f"KOSPI data: {len(kospi)} days, latest: {kospi['close'].iloc[-1]:,.0f}")
        return kospi

    except Exception as e:
        logger.error(f"Failed to get KOSPI data: {e}")
        return None


def predict_market_returns(
    kospi_data: pd.DataFrame,
    config,
) -> dict[str, float]:
    """Predict market (KOSPI) returns for each horizon.

    Args:
        kospi_data: KOSPI index DataFrame
        config: Configuration object

    Returns:
        Dictionary of {horizon: predicted_return}
    """
    from src.core.inference import InferenceEngine

    # Create a dict like stock data
    market_data = {"KOSPI": kospi_data}

    # Run inference on KOSPI
    engine = InferenceEngine(config)
    predictions = engine.run_inference(market_data)

    # Extract returns for each horizon
    market_returns = {}
    if "KOSPI" in predictions:
        kospi_pred = predictions["KOSPI"]
        current_price = kospi_pred.current_price

        for model_name, model_pred in kospi_pred.models.items():
            for horizon_name, h_pred in model_pred.horizons.items():
                if h_pred.predicted_price and current_price > 0:
                    ret = (h_pred.predicted_price - current_price) / current_price
                    if horizon_name not in market_returns:
                        market_returns[horizon_name] = []
                    market_returns[horizon_name].append(ret)

    # Average across models
    avg_returns = {}
    for horizon, returns in market_returns.items():
        avg_returns[horizon] = sum(returns) / len(returns) if returns else 0.0
        logger.info(f"  KOSPI {horizon}: {avg_returns[horizon]*100:+.2f}%")

    return avg_returns


def apply_delta_scoring(
    scores: dict,
    market_returns: dict[str, float],
) -> None:
    """Apply delta scoring (stock return - market return).

    Modifies scores in-place to use delta returns.

    Args:
        scores: Dictionary of {code: StockScore}
        market_returns: Dictionary of {horizon: market_return}
    """
    for code, score in scores.items():
        # Calculate delta for each horizon
        if "short" in market_returns:
            score.short_return -= market_returns["short"]
        if "mid" in market_returns:
            score.mid_return -= market_returns["mid"]
        if "long" in market_returns:
            score.long_return -= market_returns["long"]

    logger.info(f"Applied delta scoring (vs KOSPI) to {len(scores)} stocks")


def get_latest_source_csvs() -> dict[str, Path | None]:
    """Get the latest CSV file from each source directory.

    Returns:
        Dictionary of {source_name: latest_file_path}
    """
    latest_files = {}

    for source, directory in SOURCE_DIRS.items():
        if not directory.exists():
            logger.warning(f"Source directory not found: {directory}")
            latest_files[source] = None
            continue

        # Find all top30 CSV files and get the most recent
        files = list(directory.glob("top30*.csv"))
        if files:
            # Sort by modification time (most recent first)
            files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            latest_files[source] = files[0]
            logger.info(f"  {source}: {files[0].name}")
        else:
            latest_files[source] = None
            logger.warning(f"  {source}: No CSV files found")

    return latest_files


def copy_source_csvs_to_docs(docs_dir: Path) -> list[Path]:
    """Copy latest source CSVs to docs/sources/ directory.

    Args:
        docs_dir: Documentation directory (docs/)

    Returns:
        List of copied file paths
    """
    sources_dir = docs_dir / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)

    latest_files = get_latest_source_csvs()
    copied = []

    for source, filepath in latest_files.items():
        if filepath and filepath.exists():
            # Copy with source prefix for clarity
            dest_name = f"{source}_{filepath.name}"
            dest_path = sources_dir / dest_name
            shutil.copy2(filepath, dest_path)
            copied.append(dest_path)
            logger.info(f"  Copied: {dest_name}")

    return copied


def aggregate_candidates(days: int = 10) -> tuple[list[str], dict[str, str], dict[str, int]]:
    """Aggregate stock candidates from all sources.

    Args:
        days: Number of days to look back

    Returns:
        Tuple of (code_list, name_map, freq_counts)
    """
    # Frequency counter for each stock
    freq_counts: dict[str, int] = defaultdict(int)
    name_map: dict[str, str] = {}

    for source, directory in SOURCE_DIRS.items():
        logger.info(f"Scanning {source}: {directory}")

        files = get_latest_files_per_day(directory, days)
        logger.info(f"  Found {len(files)} files")

        for filepath in files:
            stocks = load_stocks_from_csv(filepath, source)
            for stock in stocks:
                code = stock["code"]
                freq_counts[code] += 1
                if code not in name_map:
                    name_map[code] = stock["name"]

    # Sort by frequency and take top candidates
    sorted_codes = sorted(freq_counts.keys(), key=lambda x: freq_counts[x], reverse=True)

    logger.info(f"Total unique stocks: {len(sorted_codes)}")
    logger.info(f"Top 10 by frequency:")
    for code in sorted_codes[:10]:
        logger.info(f"  {code} ({name_map.get(code, '')}): {freq_counts[code]} times")

    return sorted_codes, name_map, dict(freq_counts)


def run_ensemble_scanner(
    top_n: int = 30,
    days: int = 10,
    dry_run: bool = False,
    github_repo: str | None = None,
    push: bool = True,
) -> None:
    """Run the ensemble stock scanner with multi-source aggregation.

    Args:
        top_n: Number of top stocks to return
        days: Number of days to look back for candidates
        dry_run: If True, skip actual model inference
        github_repo: GitHub repository URL for Pages deployment
        push: If True, push to GitHub Pages
    """
    logger.info("=" * 60)
    logger.info("Deep-Ensemble Stock Scanner v3.0")
    logger.info("=" * 60)

    # Load config
    config_path = Path(__file__).parent / "config" / "config.yaml"
    config = load_config(config_path)
    logger.info(f"Loaded config: {config.models}")

    # Aggregate candidates from all sources
    logger.info(f"\n[1/7] Aggregating candidates from {len(SOURCE_DIRS)} sources ({days} days)...")
    codes, name_map, freq_counts = aggregate_candidates(days)

    if not codes:
        logger.error("No candidates found!")
        return

    # Filter by market cap (>= 1000억원)
    logger.info(f"\n[2/7] Filtering by market cap (>= 1000억원)...")
    filtered_codes = filter_by_market_cap(codes, min_market_cap=1000)
    logger.info(f"After market cap filter: {len(filtered_codes)}/{len(codes)} stocks")

    if not filtered_codes:
        logger.error("No stocks passed market cap filter!")
        return

    # Take top candidates by frequency for processing
    # Limit to top 50 to keep inference time reasonable
    max_candidates = 50
    candidate_codes = filtered_codes[:max_candidates]
    logger.info(f"Processing top {len(candidate_codes)} candidates by frequency")

    # Collect price data
    logger.info(f"\n[3/7] Collecting price data...")
    collector = DataCollector(config.data)
    price_data = collector.collect(candidate_codes)

    valid_codes = [c for c in candidate_codes if c in price_data]
    logger.info(f"Valid stocks with price data: {len(valid_codes)}/{len(candidate_codes)}")

    if not valid_codes:
        logger.error("No valid price data collected!")
        return

    # Run inference on stocks
    logger.info(f"\n[4/7] Running model inference on stocks...")
    market_returns = {}
    if dry_run:
        logger.info("  DRY-RUN mode: Skipping actual inference")
        # Create dummy predictions
        predictions = {}
        for code in valid_codes:
            pred = StockPredictions(code=code, current_price=price_data[code]["close"].iloc[-1])
            predictions[code] = pred
    else:
        engine = InferenceEngine(config)
        predictions = engine.run_inference(price_data)

        # Predict market (KOSPI) returns for delta scoring
        logger.info(f"\n[5/7] Predicting market (KOSPI) returns...")
        kospi_data = get_kospi_data(config.data.collection_days)
        if kospi_data is not None:
            market_returns = predict_market_returns(kospi_data, config)
        else:
            logger.warning("Skipping delta scoring - no KOSPI data")

    # Score stocks
    logger.info(f"\n[6/7] Scoring stocks...")
    scorer = Scorer(config)
    scores = scorer.score_all(predictions, name_map, freq_counts)

    # Apply delta scoring (subtract market returns)
    if market_returns:
        apply_delta_scoring(scores, market_returns)

    # Assign tags (based on delta returns now)
    for score in scores.values():
        score.tag = assign_tag(score)

    # Rank stocks
    ranked = scorer.rank_stocks(scores, top_n)

    # Generate report
    logger.info(f"\n[7/8] Generating reports...")
    output_dir = Path("outputs")
    reporter = Reporter(output_dir)

    outputs = reporter.generate_report(ranked, top_n=top_n)

    logger.info(f"\nResults saved to:")
    for report_type, path in outputs.items():
        logger.info(f"  {report_type}: {path}")

    # GitHub Pages deployment
    logger.info(f"\n[8/8] GitHub Pages deployment...")
    if github_repo:
        import pandas as pd
        from datetime import date as date_type

        # Read the CSV for HTML generation
        csv_path = outputs.get("main")
        if csv_path and csv_path.exists():
            df = pd.read_csv(csv_path)
            pages_dir = Path("docs")

            # Generate HTML pages
            html_outputs = generate_html_pages(
                df=df,
                as_of_date=date_type.today(),
                top_n=top_n,
                pages_dir=pages_dir,
                github_repo=github_repo,
                result_csv=csv_path.name,
            )
            logger.info(f"HTML generated: {list(html_outputs.keys())}")

            # Copy source CSVs to docs/sources/
            logger.info("Copying source CSVs...")
            copied_csvs = copy_source_csvs_to_docs(pages_dir)
            logger.info(f"Copied {len(copied_csvs)} source CSVs")

            # Copy ensemble result CSV to docs/
            ensemble_dest = pages_dir / csv_path.name
            shutil.copy2(csv_path, ensemble_dest)
            logger.info(f"Copied ensemble result: {csv_path.name}")

            # Publish to GitHub Pages
            if push:
                success = publish_to_github_pages(
                    as_of_date=date_type.today(),
                    push=True,
                    repo_url=github_repo,
                )
                if success:
                    logger.info("GitHub Pages deployment complete")
                else:
                    logger.warning("GitHub Pages deployment failed")
        else:
            logger.warning("No CSV output found, skipping HTML generation")
    else:
        logger.info("No github_repo specified, skipping deployment")

    logger.info("\n" + "=" * 60)
    logger.info("Ensemble scanning complete!")
    logger.info("=" * 60)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Deep-Ensemble Stock Scanner with Multi-Source Aggregation"
    )
    parser.add_argument(
        "--top-n", type=int, default=30,
        help="Number of top stocks to return (default: 30)"
    )
    parser.add_argument(
        "--days", type=int, default=10,
        help="Number of days to look back for candidates (default: 10)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Skip actual model inference (for testing)"
    )
    parser.add_argument(
        "--github-repo",
        default="github.com/avantchoi82/chronosbolt-moirai-ttm",
        help="GitHub repository URL for Pages deployment (default: github.com/avantchoi82/chronosbolt-moirai-ttm)"
    )
    parser.add_argument(
        "--push", action="store_true",
        help="Push to GitHub after generating HTML (default: no push)"
    )

    args = parser.parse_args()

    run_ensemble_scanner(
        top_n=args.top_n,
        days=args.days,
        dry_run=args.dry_run,
        github_repo=args.github_repo,
        push=args.push,
    )


if __name__ == "__main__":
    main()
