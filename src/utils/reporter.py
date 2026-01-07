"""Reporting and output generation.

Implements CONSTITUTION.md 제23조~제24조.
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from src.core.scorer import StockScore

logger = logging.getLogger("ensemble")
console = Console()


def get_output_filename(prefix: str = "top30") -> str:
    """Generate timestamped output filename.

    Format: top30_yyyy_mm_dd_hhmm.csv

    Args:
        prefix: File prefix

    Returns:
        Filename with timestamp
    """
    timestamp = datetime.now().strftime("%Y_%m_%d_%H%M")
    return f"{prefix}_{timestamp}.csv"


def save_result_csv(
    scores: list[StockScore],
    output_dir: str | Path,
    filename: str | None = None,
) -> Path:
    """Save results to CSV file (제23조).

    Columns: rank, code, name, current_price, short_ret, mid_ret, long_ret,
             daily_return, agreement, total_score, tag, freq_count

    Args:
        scores: List of StockScore (ranked)
        output_dir: Output directory
        filename: Optional filename (auto-generated if None)

    Returns:
        Path to saved file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if filename is None:
        filename = get_output_filename("top30")

    filepath = output_dir / filename

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            "rank",
            "code",
            "name",
            "current_price",
            "short_ret",
            "mid_ret",
            "long_ret",
            "daily_return",
            "agreement",
            "total_score",
            "tag",
            "freq_count",
        ])

        # Data rows
        for rank, score in enumerate(scores, 1):
            writer.writerow([
                rank,
                score.code,
                score.name,
                int(score.current_price),
                f"{score.short_return * 100:.2f}",
                f"{score.mid_return * 100:.2f}",
                f"{score.long_return * 100:.2f}",
                f"{score.weighted_daily_return * 100:.4f}",
                f"{score.avg_agreement:.3f}",
                f"{score.final_score:.6f}",
                score.tag,
                score.freq_count,
            ])

    logger.info(f"Results saved to: {filepath}")
    return filepath


def save_detail_log(
    scores: list[StockScore],
    output_dir: str | Path,
    filename: str | None = None,
) -> Path:
    """Save detailed results with per-model predictions.

    Args:
        scores: List of StockScore
        output_dir: Output directory
        filename: Optional filename

    Returns:
        Path to saved file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if filename is None:
        filename = get_output_filename("top30_detail")

    filepath = output_dir / filename

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)

        # Header with model-specific columns
        writer.writerow([
            "rank",
            "code",
            "name",
            "current_price",
            # Chronos
            "chronos_short",
            "chronos_mid",
            "chronos_long",
            # TTM
            "ttm_short",
            "ttm_mid",
            "ttm_long",
            # Moirai
            "moirai_short",
            "moirai_mid",
            "moirai_long",
            # Ensemble
            "ensemble_short",
            "ensemble_mid",
            "ensemble_long",
            # Scores
            "daily_return",
            "agreement_short",
            "agreement_mid",
            "agreement_long",
            "avg_agreement",
            "freq_bonus",
            "final_score",
            "tag",
        ])

        for rank, score in enumerate(scores, 1):
            row = [
                rank,
                score.code,
                score.name,
                int(score.current_price),
            ]

            # Model returns per horizon
            for model in ["Chronos", "TTM", "Moirai"]:
                for horizon in ["short", "mid", "long"]:
                    if horizon in score.horizons:
                        model_ret = score.horizons[horizon].model_returns.get(model)
                        row.append(f"{model_ret * 100:.2f}" if model_ret is not None else "")
                    else:
                        row.append("")

            # Ensemble returns
            row.append(f"{score.short_return * 100:.2f}")
            row.append(f"{score.mid_return * 100:.2f}")
            row.append(f"{score.long_return * 100:.2f}")

            # Scores
            row.append(f"{score.weighted_daily_return * 100:.4f}")

            # Per-horizon agreement
            for horizon in ["short", "mid", "long"]:
                if horizon in score.horizons:
                    row.append(f"{score.horizons[horizon].agreement:.3f}")
                else:
                    row.append("")

            row.append(f"{score.avg_agreement:.3f}")
            row.append(f"{score.freq_bonus:.4f}")
            row.append(f"{score.final_score:.6f}")
            row.append(score.tag)

            writer.writerow(row)

    logger.info(f"Detail log saved to: {filepath}")
    return filepath


def _get_tag_style(tag: str) -> str:
    """Get Rich style for tag."""
    tag_styles = {
        "Short-term Surge": "bold red",
        "Long-term Growth": "bold green",
        "High Confidence": "bold cyan",
        "Balanced": "bold blue",
        "Mixed": "dim",
    }
    return tag_styles.get(tag, "")


def _format_return(value: float) -> Text:
    """Format return value with color."""
    pct = value * 100
    if pct > 0:
        return Text(f"+{pct:.1f}%", style="green")
    elif pct < 0:
        return Text(f"{pct:.1f}%", style="red")
    else:
        return Text("0.0%", style="dim")


def print_terminal_report(
    scores: list[StockScore],
    stats: dict | None = None,
    top_n: int = 30,
) -> None:
    """Print simple text report to terminal (제23조).

    Args:
        scores: List of StockScore (ranked)
        stats: Optional execution statistics
        top_n: Number of top stocks to display
    """
    console.print()
    console.print("[bold cyan]Deep-Ensemble Stock Scanner v3.0[/bold cyan]")
    console.print("[dim]All Zero-shot Foundation Models Edition[/dim]")
    console.print()
    console.print(f"[bold]TOP {top_n} Recommended Stocks[/bold]")
    console.print("-" * 100)

    # Header
    header = f"{'Rank':>4}  {'Code':<8}  {'Name':<16}  {'Price':>12}  {'Short':>8}  {'Mid':>8}  {'Long':>8}  {'Agree':>6}  {'Score':>8}  {'Type':<16}"
    console.print(header)
    console.print("-" * 100)

    for rank, score in enumerate(scores[:top_n], 1):
        # Format values (multiply by 100 for percentage display)
        short_pct = f"{score.short_return * 100:+.1f}%" if score.short_return else "0.0%"
        mid_pct = f"{score.mid_return * 100:+.1f}%" if score.mid_return else "0.0%"
        long_pct = f"{score.long_return * 100:+.1f}%" if score.long_return else "0.0%"
        agree_text = f"{score.avg_agreement:.2f}"
        score_text = f"{score.final_score:.4f}"

        # Color for type
        tag_style = _get_tag_style(score.tag)
        tag_text = f"[{tag_style}]{score.tag}[/{tag_style}]"

        line = f"{rank:>4}  {score.code:<8}  {score.name:<16}  {int(score.current_price):>12,}  {short_pct:>8}  {mid_pct:>8}  {long_pct:>8}  {agree_text:>6}  {score_text:>8}  {tag_text}"
        console.print(line)

    console.print("-" * 100)
    console.print()

    # Statistics panel
    if stats:
        stats_text = (
            f"[bold]Execution Statistics[/bold]\n\n"
            f"Input stocks: {stats.get('input_count', 'N/A')}\n"
            f"After filter: {stats.get('filtered_count', 'N/A')}\n"
            f"Processing time: {stats.get('elapsed_time', 'N/A')}\n"
            f"Models used: {', '.join(stats.get('models_used', []))}"
        )
        console.print(Panel(stats_text, border_style="green"))
        console.print()

    # Tag legend
    legend_text = (
        "[bold]Investment Type Legend:[/bold]\n"
        "[bold red]Short-term Surge[/bold red]: Short > 5% AND Short > Long\n"
        "[bold green]Long-term Growth[/bold green]: Long > 15% AND Long > Short x 1.5\n"
        "[bold cyan]High Confidence[/bold cyan]: Model Agreement > 85%\n"
        "[bold blue]Balanced[/bold blue]: Both Short & Long positive\n"
        "[dim]Mixed[/dim]: Other patterns"
    )
    console.print(Panel(legend_text, title="Legend", border_style="dim"))
    console.print()

    # Disclaimer
    console.print(
        "[dim italic]Disclaimer: This is for reference only. "
        "Past performance does not guarantee future returns. "
        "Please diversify and invest within your means.[/dim italic]"
    )
    console.print()


def print_summary(
    input_count: int,
    filtered_count: int,
    output_count: int,
    elapsed_seconds: float,
    models_used: list[str],
) -> None:
    """Print execution summary.

    Args:
        input_count: Number of input stocks
        filtered_count: Number after filtering
        output_count: Number of final results
        elapsed_seconds: Total execution time
        models_used: List of model names used
    """
    console.print()
    console.print("[bold cyan]Execution Summary[/bold cyan]")
    console.print(f"  Input stocks:     {input_count}")
    console.print(f"  After filtering:  {filtered_count}")
    console.print(f"  Final results:    {output_count}")
    console.print(f"  Total time:       {elapsed_seconds:.1f}s")
    console.print(f"  Models:           {', '.join(models_used)}")
    console.print()


class Reporter:
    """Reporter for generating all outputs."""

    def __init__(self, output_dir: str | Path):
        """Initialize reporter.

        Args:
            output_dir: Directory for output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        scores: list[StockScore],
        stats: dict | None = None,
        save_csv: bool = True,
        save_detail: bool = True,
        print_console: bool = True,
        top_n: int = 30,
    ) -> dict[str, Path]:
        """Generate all reports.

        Args:
            scores: List of StockScore (ranked)
            stats: Execution statistics
            save_csv: Save main CSV
            save_detail: Save detail CSV
            print_console: Print to terminal
            top_n: Number of top stocks to display

        Returns:
            Dictionary of {report_type: filepath}
        """
        outputs = {}

        if save_csv:
            outputs["main"] = save_result_csv(scores, self.output_dir)

        if save_detail:
            outputs["detail"] = save_detail_log(scores, self.output_dir)

        if print_console:
            print_terminal_report(scores, stats, top_n)

        return outputs
