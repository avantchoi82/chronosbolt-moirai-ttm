"""Git Update Tool for stock scanner sources.

Copies CSV files from linked projects and publishes to GitHub Pages.
  - chartking: output
  - real: output (CAP only)
  - etfking: output (macro ETF data)
  - fred: outputs (liquidity dashboard PNG)
  - real_minute: output (60-minute candle)

Usage:
  python main.py          # Generate HTML only
  python main.py --push   # Generate HTML and push to GitHub
"""

from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime, date
import shutil

import pandas as pd

from src.utils.html_generator import generate_html_pages
from src.utils.github_publisher import publish_to_github_pages
from src.utils.stock_analyzer import analyze_all_sources

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("git_updater")

# Source directories configuration
SOURCE_DIRS = {
    "chartking": Path(r"C:\Users\user\PycharmProjects\chartking\output"),
}

# Real source directory (for CAP only, ATR excluded)
REAL_SOURCE_DIR = Path(r"C:\Users\user\PycharmProjects\real\output")

# Macro (ETF) source directory
MACRO_SOURCE_DIR = Path(r"C:\Users\user\PycharmProjects\etfking\output")


# FRED source directory (liquidity dashboard)
FRED_SOURCE_DIR = Path(r"C:\Users\user\PycharmProjects\fred\outputs")

# KOSPIDISPART source directory (KOSPI market status)
KOSPIDISPART_SOURCE_DIR = Path(r"C:\Users\user\PycharmProjects\kospidispart\results\daily_logs")


# KOFIA source directory (신용비율 그래프)
KOFIA_SOURCE_DIR = Path(r"C:\Users\user\PycharmProjects\kofia\downloads")

# AboutKosdaq source directory (코스닥 일봉 차트)
ABOUTKOSDAQ_SOURCE_DIR = Path(r"C:\Users\user\PycharmProjects\aboutkosdaq")

# Real Minute source directory (60분봉 데이터)
REAL_MINUTE_SOURCE_DIR = Path(r"C:\Users\user\PycharmProjects\real_minute\output")

# XGBOOST source directory
XGBOOST_SOURCE_DIR = Path(r"C:\Users\user\PycharmProjects\xgboost\output")

# Output directory
DOCS_DIR = Path(__file__).parent / "docs"


def get_latest_kospidispart_txt() -> Path | None:
    """Get the latest KOSPIDISPART txt file (KOSPI market status).

    Returns:
        Path to latest file or None if not found
    """
    if not KOSPIDISPART_SOURCE_DIR.exists():
        logger.warning(f"KOSPIDISPART source directory not found: {KOSPIDISPART_SOURCE_DIR}")
        return None

    # Find txt files (format: YYYYMMDD.txt)
    files = list(KOSPIDISPART_SOURCE_DIR.glob("*.txt"))

    if files:
        # Sort by filename (which is date-based) in descending order
        files.sort(key=lambda f: f.stem, reverse=True)
        latest = files[0]
        logger.info(f"  kospidispart: {latest.name}")
        return latest
    else:
        logger.warning("  kospidispart: No txt files found")
        return None


def get_latest_real_cap_csv() -> Path | None:
    """Get the latest Real CAP CSV file (top30_cap_*.csv).

    Returns:
        Path to latest file or None if not found
    """
    if not REAL_SOURCE_DIR.exists():
        logger.warning(f"Real source directory not found: {REAL_SOURCE_DIR}")
        return None

    # Find top30_cap CSV files
    files = list(REAL_SOURCE_DIR.glob("top30_cap_*.csv"))

    if files:
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        latest = files[0]
        logger.info(f"  real (CAP): {latest.name}")
        return latest
    else:
        logger.warning("  real (CAP): No CSV files found")
        return None


def get_latest_minute60_csv() -> Path | None:
    """Get the latest minute60 CSV file (60-minute candle data).

    Returns:
        Path to latest file or None if not found
    """
    if not REAL_MINUTE_SOURCE_DIR.exists():
        logger.warning(f"Real Minute source directory not found: {REAL_MINUTE_SOURCE_DIR}")
        return None

    # Find minute60_*.csv files
    files = list(REAL_MINUTE_SOURCE_DIR.glob("minute60_*.csv"))

    if files:
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        latest = files[0]
        logger.info(f"  minute60: {latest.name}")
        return latest
    else:
        logger.warning("  minute60: No CSV files found")
        return None


def get_latest_source_csvs() -> dict[str, Path | None]:
    """Get the latest CSV file from each source directory.

    Returns:
        Dictionary of {source_name: latest_file_path}
    """
    latest_files = {}

    # Define glob patterns per source
    glob_patterns = {
        "chartking": "top30_lev_wfo_*.csv",
    }

    for source, directory in SOURCE_DIRS.items():
        if not directory.exists():
            logger.warning(f"Source directory not found: {directory}")
            latest_files[source] = None
            continue

        # Find CSV files using source-specific pattern
        pattern = glob_patterns.get(source, "top30*.csv")
        files = list(directory.glob(pattern))
        if files:
            files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            latest_files[source] = files[0]
            logger.info(f"  {source}: {files[0].name}")
        else:
            latest_files[source] = None
            logger.warning(f"  {source}: No CSV files found")

    return latest_files


def get_latest_macro_csv() -> Path | None:
    """Get the latest US ETF CSV file from etfking directory.

    Returns:
        Path to latest file or None if not found
    """
    if not MACRO_SOURCE_DIR.exists():
        logger.warning(f"Macro source directory not found: {MACRO_SOURCE_DIR}")
        return None

    # Find today's latest top30 CSV file
    today_str = datetime.now().strftime("%Y_%m_%d")
    files = list(MACRO_SOURCE_DIR.glob(f"top30_{today_str}_*.csv"))

    if not files:
        # Fallback: get most recent file regardless of date
        files = list(MACRO_SOURCE_DIR.glob("top30*.csv"))

    if files:
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        latest = files[0]
        logger.info(f"  etfking US (macro): {latest.name}")
        return latest
    else:
        logger.warning("  etfking US (macro): No CSV files found")
        return None


def get_latest_korea_macro_csv() -> Path | None:
    """Get the latest Korea ETF sector CSV file from etfking directory.

    Returns:
        Path to latest file or None if not found
    """
    if not MACRO_SOURCE_DIR.exists():
        logger.warning(f"Macro source directory not found: {MACRO_SOURCE_DIR}")
        return None

    # Find korea_sector CSV files
    files = list(MACRO_SOURCE_DIR.glob("korea_sector_*.csv"))

    if files:
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        latest = files[0]
        logger.info(f"  etfking Korea (macro): {latest.name}")
        return latest
    else:
        logger.warning("  etfking Korea (macro): No CSV files found")
        return None


def get_kospi_regime_csv() -> Path | None:
    """Get the kospi_regime.csv from chartking output directory."""
    chartking_dir = SOURCE_DIRS["chartking"]
    if not chartking_dir.exists():
        logger.warning(f"Chartking source directory not found: {chartking_dir}")
        return None

    regime_path = chartking_dir / "kospi_regime.csv"
    if regime_path.exists():
        logger.info(f"  kospi_regime: {regime_path.name}")
        return regime_path
    else:
        logger.warning("  kospi_regime: kospi_regime.csv not found")
        return None


def get_latest_xgboost_csv() -> Path | None:
    """Get the latest XGBOOST top20 CSV file.

    Returns:
        Path to latest file or None if not found
    """
    if not XGBOOST_SOURCE_DIR.exists():
        logger.warning(f"XGBOOST source directory not found: {XGBOOST_SOURCE_DIR}")
        return None

    # Find top20 CSV files
    files = list(XGBOOST_SOURCE_DIR.glob("top20_*.csv"))

    if files:
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        latest = files[0]
        logger.info(f"  xgboost: {latest.name}")
        return latest
    else:
        logger.warning("  xgboost: No CSV files found")
        return None


def get_latest_fred_png() -> Path | None:
    """Get the latest FRED liquidity dashboard PNG file.

    Returns:
        Path to latest file or None if not found
    """
    if not FRED_SOURCE_DIR.exists():
        logger.warning(f"FRED source directory not found: {FRED_SOURCE_DIR}")
        return None

    # Find PNG files
    files = list(FRED_SOURCE_DIR.glob("*.png"))

    if files:
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        latest = files[0]
        logger.info(f"  fred: {latest.name}")
        return latest
    else:
        logger.warning("  fred: No PNG files found")
        return None


def get_kofia_png() -> Path | None:
    """Get the KOFIA 신용비율 그래프 PNG file.

    Returns:
        Path to file or None if not found
    """
    if not KOFIA_SOURCE_DIR.exists():
        logger.warning(f"KOFIA source directory not found: {KOFIA_SOURCE_DIR}")
        return None

    # Find the specific PNG file
    png_path = KOFIA_SOURCE_DIR / "증시자금_신용비율_그래프.png"

    if png_path.exists():
        logger.info(f"  kofia: {png_path.name}")
        return png_path
    else:
        logger.warning("  kofia: PNG file not found")
        return None


def get_aboutkosdaq_png() -> Path | None:
    """Get the AboutKosdaq 코스닥 일봉 차트 PNG file.

    Returns:
        Path to file or None if not found
    """
    if not ABOUTKOSDAQ_SOURCE_DIR.exists():
        logger.warning(f"AboutKosdaq source directory not found: {ABOUTKOSDAQ_SOURCE_DIR}")
        return None

    png_path = ABOUTKOSDAQ_SOURCE_DIR / "kosdaq_daily_chart.png"

    if png_path.exists():
        logger.info(f"  aboutkosdaq: {png_path.name}")
        return png_path
    else:
        logger.warning("  aboutkosdaq: PNG file not found")
        return None


def _copy_if_newer(src: Path, dest: Path) -> bool:
    """Copy file only if source is newer than destination."""
    if not dest.exists():
        shutil.copy2(src, dest)
        return True
    if src.stat().st_mtime > dest.stat().st_mtime:
        shutil.copy2(src, dest)
        return True
    return False


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
            dest_name = f"{source}_{filepath.name}"
            dest_path = sources_dir / dest_name
            if _copy_if_newer(filepath, dest_path):
                copied.append(dest_path)
                logger.info(f"  Copied: {dest_name}")

    # Copy macro (US ETF) CSV
    macro_csv = get_latest_macro_csv()
    if macro_csv and macro_csv.exists():
        dest_name = f"etfking_{macro_csv.name}"
        dest_path = sources_dir / dest_name
        if _copy_if_newer(macro_csv, dest_path):
            copied.append(dest_path)
            logger.info(f"  Copied: {dest_name}")

    # Copy Korea ETF sector CSV
    korea_csv = get_latest_korea_macro_csv()
    if korea_csv and korea_csv.exists():
        dest_name = f"etfking_{korea_csv.name}"
        dest_path = sources_dir / dest_name
        if _copy_if_newer(korea_csv, dest_path):
            copied.append(dest_path)
            logger.info(f"  Copied: {dest_name}")

    # Copy FRED PNG to docs/images/
    images_dir = docs_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    fred_png = get_latest_fred_png()
    if fred_png and fred_png.exists():
        dest_name = "fred_liquidity_dashboard.png"
        dest_path = images_dir / dest_name
        if _copy_if_newer(fred_png, dest_path):
            copied.append(dest_path)
            logger.info(f"  Copied: {dest_name}")

    # Copy KOFIA PNG to docs/images/ (always copy - updates frequently)
    kofia_png = get_kofia_png()
    if kofia_png and kofia_png.exists():
        dest_name = "kofia_credit_ratio.png"
        dest_path = images_dir / dest_name
        shutil.copy2(kofia_png, dest_path)
        copied.append(dest_path)
        logger.info(f"  Copied: {dest_name}")

    # Copy AboutKosdaq PNG to docs/images/ (always copy - updates frequently)
    aboutkosdaq_png = get_aboutkosdaq_png()
    if aboutkosdaq_png and aboutkosdaq_png.exists():
        dest_name = "kosdaq_daily_chart.png"
        dest_path = images_dir / dest_name
        shutil.copy2(aboutkosdaq_png, dest_path)
        copied.append(dest_path)
        logger.info(f"  Copied: {dest_name}")

    # Copy AboutKosdaq backtest images to docs/images/ (always copy)
    backtest_images = [
        ("kosdaq_backtest_ma_standard.png", "kosdaq_backtest_ma_standard.png"),
        ("kosdaq_backtest_ma_cross.png", "kosdaq_backtest_ma_cross.png"),
        ("kosdaq_weekly_surge_analysis.png", "kosdaq_weekly_surge_analysis.png"),
    ]
    for src_name, dest_name in backtest_images:
        src_path = ABOUTKOSDAQ_SOURCE_DIR / src_name
        if src_path.exists():
            dest_path = images_dir / dest_name
            shutil.copy2(src_path, dest_path)
            copied.append(dest_path)
            logger.info(f"  Copied: {dest_name}")

    return copied


def run_git_update(
    github_repo: str = "github.com/avantchoi82/chronosbolt-moirai-ttm",
    push: bool = False,
    enable_ai: bool = False,
) -> None:
    """Run git update - copy CSVs, generate HTML, and optionally push.

    Args:
        github_repo: GitHub repository URL for Pages deployment
        push: If True, push to GitHub Pages
        enable_ai: If True, generate AI summaries for top 10 stocks
    """
    logger.info("GitHub upload and HTML generation has been disabled by user request.")
    return

    logger.info("=" * 60)
    logger.info("Git Update Tool - CSV & HTML Publisher")
    logger.info("=" * 60)

    today = date.today()

    # Step 1: Get KOSPIDISPART txt (KOSPI market status)
    logger.info("\n[1/10] Finding latest KOSPIDISPART txt...")
    kospidispart_txt = get_latest_kospidispart_txt()

    # Step 2: Get source CSVs (chartking, real ATR)
    logger.info("\n[2/10] Finding latest source CSVs...")
    source_csvs = get_latest_source_csvs()

    # Step 2b: Get KOSPI Regime CSV
    logger.info("\n[2b/10] Finding KOSPI regime CSV...")
    kospi_regime_csv = get_kospi_regime_csv()

    # Step 3: Get Real CAP CSV
    logger.info("\n[3/10] Finding latest Real CAP CSV...")
    real_cap_csv = get_latest_real_cap_csv()

    # Step 4: Get Minute60 CSV (60-minute candle data)
    logger.info("\n[4/10] Finding latest Minute60 CSV...")
    minute60_csv = get_latest_minute60_csv()

    # Step 5: Get macro CSVs
    logger.info("\n[5/10] Finding latest macro CSVs...")
    macro_csv = get_latest_macro_csv()
    korea_macro_csv = get_latest_korea_macro_csv()


    # Step 7: Get XGBOOST CSV
    logger.info("\n[7/11] Finding latest XGBOOST CSV...")
    xgboost_csv = get_latest_xgboost_csv()

    # Step 8: Get FRED PNG
    logger.info("\n[7/9] Finding latest FRED PNG...")
    fred_png = get_latest_fred_png()

    # Step 9: Copy files to docs/
    logger.info("\n[8/11] Copying files to docs/...")
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Copy source CSVs
    sources_dir = DOCS_DIR / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    
    copied_files = copy_source_csvs_to_docs(DOCS_DIR)
    
    # Copy XGBOOST CSV if available
    if xgboost_csv and xgboost_csv.exists():
        _copy_if_newer(xgboost_csv, sources_dir / xgboost_csv.name)
        copied_files.append(sources_dir / xgboost_csv.name)
        
    logger.info(f"Copied {len(copied_files)} files")

    # Step 10: AI Analysis (news + summary) for top 10 stocks
    stock_summaries = None
    if enable_ai:
        logger.info("\n[9/11] Analyzing stocks with AI (top 10 per source)...")
        try:
            stock_summaries = analyze_all_sources(
                source_csvs=source_csvs,
                xgboost_csv=None,
                top_n=10,
                enable_ai=True,
            )
            total_summaries = sum(len(s) for s in stock_summaries.values())
            logger.info(f"Generated {total_summaries} AI summaries")
        except Exception as e:
            logger.warning(f"AI analysis failed: {e}")
            stock_summaries = None
    else:
        logger.info("\n[9/11] Skipping AI analysis (use --ai to enable)")

    # Step 11: Generate HTML pages
    logger.info("\n[10/11] Generating HTML pages...")
    html_outputs = generate_html_pages(
        df=pd.DataFrame(),  # Empty DataFrame - no ensemble results
        as_of_date=today,
        top_n=30,
        pages_dir=DOCS_DIR,
        github_repo=github_repo,
        result_csv=None,
        source_csvs=source_csvs,
        macro_csv=macro_csv,
        korea_macro_csv=korea_macro_csv,
        fred_png=fred_png,
        stock_summaries=stock_summaries,
        kospidispart_txt=kospidispart_txt,
        real_cap_csv=real_cap_csv,
        minute60_csv=minute60_csv,
        xgboost_csv=xgboost_csv,
        kospi_regime_csv=kospi_regime_csv,
    )
    logger.info(f"HTML generated: {list(html_outputs.keys())}")

    # Step 12: Push to GitHub if requested
    if push:
        logger.info("\n[11/11] Pushing to GitHub Pages...")
        success = publish_to_github_pages(
            as_of_date=today,
            push=True,
            repo_url=github_repo,
        )
        if success:
            logger.info("GitHub Pages deployment complete")
        else:
            logger.warning("GitHub Pages deployment failed")
    else:
        logger.info("\n[11/11] Skipping push (use --push to enable)")

    logger.info("\n" + "=" * 60)
    logger.info("Git update complete!")
    logger.info("=" * 60)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Git Update Tool - Copy CSVs and publish to GitHub Pages"
    )
    parser.add_argument(
        "--github-repo",
        default="github.com/avantchoi82/chronosbolt-moirai-ttm",
        help="GitHub repository URL for Pages deployment"
    )
    parser.add_argument(
        "--push", action="store_true",
        help="Push to GitHub after generating HTML"
    )
    parser.add_argument(
        "--ai", action="store_true",
        help="Enable AI news summary for top 10 stocks (requires GEMINI_API_KEY)"
    )

    args = parser.parse_args()

    run_git_update(
        github_repo=args.github_repo,
        push=args.push,
        enable_ai=args.ai,
    )


if __name__ == "__main__":
    main()
