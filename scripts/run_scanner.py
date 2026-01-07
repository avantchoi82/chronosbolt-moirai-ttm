#!/usr/bin/env python3
"""Deep-Ensemble Stock Scanner v3.0 - Main Entry Point.

All Zero-shot Foundation Models Edition.

Usage:
    python scripts/run_scanner.py --config config/config.yaml --csv candidates.csv
    python scripts/run_scanner.py --config config/config.yaml --csv data/*.csv --top 20
    python scripts/run_scanner.py --config config/config.yaml --csv data/*.csv --only-chronos
    python scripts/run_scanner.py --config config/config.yaml --csv data/*.csv --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time
from glob import glob
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console

console = Console()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Deep-Ensemble Stock Scanner v3.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to config YAML file",
    )

    parser.add_argument(
        "--csv",
        type=str,
        nargs="+",
        required=True,
        help="Path(s) to candidate CSV files (supports glob patterns)",
    )

    parser.add_argument(
        "--top",
        type=int,
        default=15,
        help="Number of top stocks to select (default: 15)",
    )

    parser.add_argument(
        "--only-chronos",
        action="store_true",
        help="Use only Chronos model (faster)",
    )

    parser.add_argument(
        "--only-ttm",
        action="store_true",
        help="Use only TTM model",
    )

    parser.add_argument(
        "--only-moirai",
        action="store_true",
        help="Use only Moirai model",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only test data collection, skip inference",
    )

    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="Skip volume/value filtering",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Override output directory",
    )

    return parser.parse_args()


def expand_csv_paths(patterns: list[str]) -> list[Path]:
    """Expand glob patterns to actual file paths."""
    paths = []
    for pattern in patterns:
        if "*" in pattern:
            expanded = glob(pattern)
            paths.extend(Path(p) for p in expanded)
        else:
            paths.append(Path(pattern))

    return [p for p in paths if p.exists()]


def main() -> int:
    """Main entry point."""
    args = parse_args()
    start_time = time.time()

    # Import after path setup
    from src.utils.config_loader import load_config
    from src.utils.logger import setup_logger
    from src.data.candidate_pool import CandidatePool
    from src.data.collector import DataCollector, get_stock_names
    from src.data.preprocessor import DataPreprocessor
    from src.core.inference import InferenceEngine
    from src.core.scorer import Scorer
    from src.core.filters import FilterPipeline, calculate_all_volume_stats, get_sector_info
    from src.utils.reporter import Reporter, print_summary

    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        return 1

    # Setup logging
    log_level = "DEBUG" if args.verbose else config.logging.level
    logger = setup_logger(
        name="ensemble",
        log_dir=config.paths.log_dir,
        level=log_level,
    )
    logger.info("Deep-Ensemble Stock Scanner v3.0 starting...")

    # Override config based on CLI args
    if args.only_chronos:
        config.models["ttm"].enabled = False
        config.models["moirai"].enabled = False
        logger.info("Using only Chronos model")
    elif args.only_ttm:
        config.models["chronos"].enabled = False
        config.models["moirai"].enabled = False
        logger.info("Using only TTM model")
    elif args.only_moirai:
        config.models["chronos"].enabled = False
        config.models["ttm"].enabled = False
        logger.info("Using only Moirai model")

    if args.top:
        config.filters.top_n = args.top

    output_dir = Path(args.output_dir) if args.output_dir else Path(config.paths.output_dir)

    # Expand CSV paths
    csv_paths = expand_csv_paths(args.csv)
    if not csv_paths:
        console.print("[red]No CSV files found![/red]")
        return 1

    logger.info(f"Found {len(csv_paths)} CSV files")

    # Step 1: Load candidate pool
    console.print("\n[bold cyan]Step 1: Loading Candidate Pool[/bold cyan]")
    pool = CandidatePool(config.filters)
    num_candidates = pool.load_from_csvs(csv_paths)

    if num_candidates == 0:
        console.print("[red]No candidates found in CSV files![/red]")
        return 1

    console.print(f"  Loaded {num_candidates} unique candidates")
    codes = pool.get_codes()
    freq_counts = pool.candidates

    # Step 2: Collect data
    console.print("\n[bold cyan]Step 2: Collecting Stock Data[/bold cyan]")
    collector = DataCollector(config.data, config.paths.cache_dir)

    from tqdm import tqdm
    with tqdm(total=len(codes), desc="Collecting") as pbar:
        def update_progress(current, total, code):
            pbar.update(1)
            pbar.set_postfix({"code": code})

        data_dict = collector.collect(codes, progress_callback=update_progress)

    console.print(f"  Collected data for {len(data_dict)} stocks")

    if args.dry_run:
        console.print("\n[yellow]Dry run complete. Skipping inference.[/yellow]")
        return 0

    # Step 3: Preprocess data
    console.print("\n[bold cyan]Step 3: Preprocessing Data[/bold cyan]")
    preprocessor = DataPreprocessor(config.data)
    processed_data, validations = preprocessor.preprocess_batch(data_dict)

    valid_count = len(processed_data)
    console.print(f"  Validated {valid_count} stocks")

    if valid_count == 0:
        console.print("[red]No valid data after preprocessing![/red]")
        return 1

    # Get stock names
    stock_names = get_stock_names(list(processed_data.keys()))

    # Step 4: Run inference
    console.print("\n[bold cyan]Step 4: Running Model Inference[/bold cyan]")
    engine = InferenceEngine(config)
    predictions = engine.run_inference(processed_data)

    console.print(f"  Generated predictions for {len(predictions)} stocks")

    # Step 5: Calculate scores
    console.print("\n[bold cyan]Step 5: Calculating Scores[/bold cyan]")
    scorer = Scorer(config)
    scores = scorer.score_all(predictions, stock_names, freq_counts)
    ranked = scorer.rank_stocks(scores)

    console.print(f"  Scored and ranked {len(ranked)} stocks")

    # Step 6: Apply filters
    console.print("\n[bold cyan]Step 6: Applying Filters[/bold cyan]")

    if args.no_filter:
        final_scores = ranked[:config.filters.top_n]
        # Assign tags manually
        from src.core.filters import assign_tags
        final_scores = assign_tags(final_scores)
    else:
        # Calculate volume stats
        volume_stats = calculate_all_volume_stats(processed_data)

        # Get sector info (optional)
        try:
            sectors = get_sector_info(list(processed_data.keys()))
        except Exception:
            sectors = None

        # Apply filter pipeline
        filter_pipeline = FilterPipeline(config.filters)
        final_scores = filter_pipeline.apply_filters(ranked, volume_stats, sectors)

    console.print(f"  Final selection: {len(final_scores)} stocks")

    # Step 7: Generate reports
    console.print("\n[bold cyan]Step 7: Generating Reports[/bold cyan]")

    elapsed_time = time.time() - start_time
    models_used = config.get_enabled_models()

    stats = {
        "input_count": num_candidates,
        "filtered_count": len(processed_data),
        "elapsed_time": f"{elapsed_time:.1f}s",
        "models_used": [m.capitalize() for m in models_used],
    }

    reporter = Reporter(output_dir)
    outputs = reporter.generate_report(
        final_scores,
        stats=stats,
        save_csv=True,
        save_detail=True,
        print_console=True,
    )

    # Print summary
    print_summary(
        input_count=num_candidates,
        filtered_count=len(processed_data),
        output_count=len(final_scores),
        elapsed_seconds=elapsed_time,
        models_used=[m.capitalize() for m in models_used],
    )

    console.print(f"[green]Results saved to: {outputs.get('main')}[/green]")
    logger.info("Scan complete!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
