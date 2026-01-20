"""Git Update Tool for stock scanner sources.

Copies CSV files from linked projects and publishes to GitHub Pages.
  - chartking: output
  - real: output
  - xgboost: output
  - etfking: output (macro ETF data)
  - fred: outputs (liquidity dashboard PNG)

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
    "real": Path(r"C:\Users\user\PycharmProjects\real\output"),
}

# Macro (ETF) source directory
MACRO_SOURCE_DIR = Path(r"C:\Users\user\PycharmProjects\etfking\output")

# XGBoost source directory
XGBOOST_SOURCE_DIR = Path(r"C:\Users\user\PycharmProjects\xgboost\output")

# LGBM source directory
LGBM_SOURCE_DIR = Path(r"C:\Users\user\PycharmProjects\lgbm\output\top30")

# FRED source directory (liquidity dashboard)
FRED_SOURCE_DIR = Path(r"C:\Users\user\PycharmProjects\fred\outputs")

# Output directory
DOCS_DIR = Path(__file__).parent / "docs"


def get_latest_source_csvs() -> dict[str, Path | None]:
    """Get the latest CSV file from each source directory.

    Returns:
        Dictionary of {source_name: latest_file_path}
    """
    latest_files = {}

    # Define glob patterns per source
    glob_patterns = {
        "chartking": "top30*.csv",
        "real": "top30_atr_*.csv",
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


def get_latest_xgboost_csv() -> Path | None:
    """Get the latest XGBoost top20 CSV file.

    Returns:
        Path to latest file or None if not found
    """
    if not XGBOOST_SOURCE_DIR.exists():
        logger.warning(f"XGBoost source directory not found: {XGBOOST_SOURCE_DIR}")
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


def get_latest_lgbm_csv() -> Path | None:
    """Get the latest LGBM top30 CSV file.

    Returns:
        Path to latest file or None if not found
    """
    if not LGBM_SOURCE_DIR.exists():
        logger.warning(f"LGBM source directory not found: {LGBM_SOURCE_DIR}")
        return None

    # Find top30 CSV files
    files = list(LGBM_SOURCE_DIR.glob("*_top30.csv"))

    if files:
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        latest = files[0]
        logger.info(f"  lgbm: {latest.name}")
        return latest
    else:
        logger.warning("  lgbm: No CSV files found")
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
            shutil.copy2(filepath, dest_path)
            copied.append(dest_path)
            logger.info(f"  Copied: {dest_name}")

    # Copy macro (US ETF) CSV
    macro_csv = get_latest_macro_csv()
    if macro_csv and macro_csv.exists():
        dest_name = f"etfking_{macro_csv.name}"
        dest_path = sources_dir / dest_name
        shutil.copy2(macro_csv, dest_path)
        copied.append(dest_path)
        logger.info(f"  Copied: {dest_name}")

    # Copy Korea ETF sector CSV
    korea_csv = get_latest_korea_macro_csv()
    if korea_csv and korea_csv.exists():
        dest_name = f"etfking_{korea_csv.name}"
        dest_path = sources_dir / dest_name
        shutil.copy2(korea_csv, dest_path)
        copied.append(dest_path)
        logger.info(f"  Copied: {dest_name}")

    # Copy XGBoost CSV
    xgboost_csv = get_latest_xgboost_csv()
    if xgboost_csv and xgboost_csv.exists():
        dest_name = f"xgboost_{xgboost_csv.name}"
        dest_path = sources_dir / dest_name
        shutil.copy2(xgboost_csv, dest_path)
        copied.append(dest_path)
        logger.info(f"  Copied: {dest_name}")

    # Copy LGBM CSV
    lgbm_csv = get_latest_lgbm_csv()
    if lgbm_csv and lgbm_csv.exists():
        dest_name = f"lgbm_{lgbm_csv.name}"
        dest_path = sources_dir / dest_name
        shutil.copy2(lgbm_csv, dest_path)
        copied.append(dest_path)
        logger.info(f"  Copied: {dest_name}")

    # Copy FRED PNG to docs/images/
    images_dir = docs_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    fred_png = get_latest_fred_png()
    if fred_png and fred_png.exists():
        dest_name = "fred_liquidity_dashboard.png"
        dest_path = images_dir / dest_name
        shutil.copy2(fred_png, dest_path)
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
    logger.info("=" * 60)
    logger.info("Git Update Tool - CSV & HTML Publisher")
    logger.info("=" * 60)

    today = date.today()

    # Step 1: Get source CSVs
    logger.info("\n[1/6] Finding latest source CSVs...")
    source_csvs = get_latest_source_csvs()

    # Step 2: Get macro CSVs
    logger.info("\n[2/6] Finding latest macro CSVs...")
    macro_csv = get_latest_macro_csv()
    korea_macro_csv = get_latest_korea_macro_csv()

    # Step 3: Get XGBoost CSV
    logger.info("\n[3/7] Finding latest XGBoost CSV...")
    xgboost_csv = get_latest_xgboost_csv()

    # Step 4: Get LGBM CSV
    logger.info("\n[4/7] Finding latest LGBM CSV...")
    lgbm_csv = get_latest_lgbm_csv()

    # Step 5: Get FRED PNG
    logger.info("\n[5/7] Finding latest FRED PNG...")
    fred_png = get_latest_fred_png()

    # Step 6: Copy files to docs/
    logger.info("\n[6/8] Copying files to docs/...")
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    copied_files = copy_source_csvs_to_docs(DOCS_DIR)
    logger.info(f"Copied {len(copied_files)} files")

    # Step 7: AI Analysis (news + summary) for top 10 stocks
    stock_summaries = None
    if enable_ai:
        logger.info("\n[7/8] Analyzing stocks with AI (top 10 per source)...")
        try:
            stock_summaries = analyze_all_sources(
                source_csvs=source_csvs,
                xgboost_csv=xgboost_csv,
                lgbm_csv=None,  # Skip LGBM for now (separate ML tab)
                top_n=10,
                enable_ai=True,
            )
            total_summaries = sum(len(s) for s in stock_summaries.values())
            logger.info(f"Generated {total_summaries} AI summaries")
        except Exception as e:
            logger.warning(f"AI analysis failed: {e}")
            stock_summaries = None
    else:
        logger.info("\n[7/8] Skipping AI analysis (use --ai to enable)")

    # Step 8: Generate HTML pages
    logger.info("\n[8/8] Generating HTML pages...")
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
        xgboost_csv=xgboost_csv,
        lgbm_csv=lgbm_csv,
        fred_png=fred_png,
        stock_summaries=stock_summaries,
    )
    logger.info(f"HTML generated: {list(html_outputs.keys())}")

    # Step 9: Push to GitHub if requested
    if push:
        logger.info("\n[9/9] Pushing to GitHub Pages...")
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
        logger.info("\n[9/9] Skipping push (use --push to enable)")

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
