"""HTML Page Generator for GitHub Pages.

Generates HTML report pages from ensemble scanner results.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger("ensemble")

# GitHub Pages 출력 디렉토리
PAGES_DIR = Path(__file__).parent.parent.parent / "docs"


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Deep-Ensemble Scanner - {date_str}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 100%);
            color: #e4e4e4;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        h1 {{
            font-size: 2rem;
            background: linear-gradient(90deg, #00d4ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 10px;
        }}
        .subtitle {{
            color: #888;
            font-size: 0.95rem;
            margin-bottom: 15px;
        }}
        .meta {{
            color: #888;
            font-size: 0.9rem;
        }}
        .meta span {{
            margin: 0 10px;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section-title {{
            font-size: 1.4rem;
            color: #00d4ff;
            margin-bottom: 15px;
            padding-left: 10px;
            border-left: 4px solid #00d4ff;
        }}
        .table-wrapper {{
            overflow-x: auto;
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}
        th {{
            background: rgba(0, 212, 255, 0.15);
            color: #00d4ff;
            padding: 12px 8px;
            text-align: left;
            font-weight: 600;
            position: sticky;
            top: 0;
            white-space: nowrap;
        }}
        td {{
            padding: 10px 8px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }}
        tr:hover {{
            background: rgba(255,255,255,0.05);
        }}
        .rank {{
            font-weight: bold;
            text-align: center;
        }}
        .rank-1 {{ color: #ffd700; }}
        .rank-2 {{ color: #c0c0c0; }}
        .rank-3 {{ color: #cd7f32; }}
        .code {{
            font-family: monospace;
            color: #00ff88;
        }}
        .name {{
            font-weight: 500;
        }}
        .positive {{
            color: #00ff88;
        }}
        .negative {{
            color: #ff4757;
        }}
        .number {{
            text-align: right;
            font-family: monospace;
        }}
        .tag {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .tag-short-term-surge {{
            background: #ff4757;
            color: white;
        }}
        .tag-long-term-growth {{
            background: #00ff88;
            color: #1a1a2e;
        }}
        .tag-high-confidence {{
            background: #00d4ff;
            color: #1a1a2e;
        }}
        .tag-balanced {{
            background: #3498db;
            color: white;
        }}
        .tag-mixed {{
            background: #555;
            color: #ccc;
        }}
        footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #666;
            font-size: 0.8rem;
        }}
        .disclaimer {{
            margin-top: 15px;
            padding: 15px;
            background: rgba(255, 71, 87, 0.1);
            border: 1px solid rgba(255, 71, 87, 0.3);
            border-radius: 8px;
            font-size: 0.8rem;
            color: #ff8888;
        }}
        .history-link {{
            margin-top: 20px;
        }}
        .history-link a {{
            color: #00d4ff;
            text-decoration: none;
            padding: 8px 16px;
            border: 1px solid #00d4ff;
            border-radius: 6px;
            transition: all 0.3s;
            margin: 0 5px;
        }}
        .history-link a:hover {{
            background: #00d4ff;
            color: #1a1a2e;
        }}
        .legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            justify-content: center;
            margin-top: 15px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 0.8rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Deep-Ensemble Stock Scanner v3.0</h1>
            <div class="subtitle">Chronos-Bolt + TTM + Moirai | Delta vs KOSPI</div>
            <div class="meta">
                <span>Date: <strong>{date_str}</strong></span>
                <span>|</span>
                <span>Generated: <strong>{generated_at}</strong></span>
            </div>
            <div class="legend">
                <div class="legend-item"><span class="tag tag-short-term-surge">Short-term Surge</span> Short &gt; 5%</div>
                <div class="legend-item"><span class="tag tag-long-term-growth">Long-term Growth</span> Long &gt; 15%</div>
                <div class="legend-item"><span class="tag tag-high-confidence">High Confidence</span> Agreement &gt; 85%</div>
                <div class="legend-item"><span class="tag tag-balanced">Balanced</span> Both positive</div>
                <div class="legend-item"><span class="tag tag-mixed">Mixed</span> Other</div>
            </div>
        </header>

        <div class="section">
            <h2 class="section-title">Top {top_n} Momentum Picks (Risk-Adjusted)</h2>
            <div class="table-wrapper">
                {top_n_table}
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">Download Data</h2>
            <div class="history-link" style="text-align: left; padding: 15px;">
                <p style="margin-bottom: 10px; color: #888;">Ensemble Result:</p>
                <a href="{result_csv}" download>📊 Ensemble Result CSV</a>
                <p style="margin: 15px 0 10px; color: #888;">Source Data (Input):</p>
                <a href="sources/" target="_blank">📁 Source CSVs (probability, chartking, real)</a>
            </div>
        </div>

        <footer>
            <p>Powered by Deep-Ensemble Stock Scanner</p>
            <p>Models: Chronos-Bolt, TTM, Moirai (Zero-shot Foundation Models)</p>
            <div class="disclaimer">
                ⚠️ 투자 참고용 자료입니다. 과거 성과가 미래 수익을 보장하지 않습니다.
                분산투자하고 감당 가능한 범위 내에서 투자하세요.
            </div>
            <div class="history-link">
                <a href="history.html">View History</a>
                <a href="https://github.com/{github_repo}">GitHub</a>
            </div>
        </footer>
    </div>
</body>
</html>
"""

HISTORY_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Deep-Ensemble Scanner - History</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 100%);
            color: #e4e4e4;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        h1 {{
            font-size: 2rem;
            color: #00d4ff;
            margin-bottom: 10px;
        }}
        .history-list {{
            list-style: none;
        }}
        .history-list li {{
            margin-bottom: 10px;
        }}
        .history-list a {{
            display: block;
            padding: 15px 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.1);
            color: #e4e4e4;
            text-decoration: none;
            transition: all 0.3s;
        }}
        .history-list a:hover {{
            background: rgba(0, 212, 255, 0.1);
            border-color: #00d4ff;
        }}
        .history-list .date {{
            color: #00d4ff;
            font-weight: bold;
        }}
        .back-link {{
            text-align: center;
            margin-top: 30px;
        }}
        .back-link a {{
            color: #00d4ff;
            text-decoration: none;
            padding: 8px 16px;
            border: 1px solid #00d4ff;
            border-radius: 6px;
        }}
        .back-link a:hover {{
            background: #00d4ff;
            color: #1a1a2e;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Result History</h1>
            <p>Deep-Ensemble Stock Scanner</p>
        </header>
        <ul class="history-list">
            {history_items}
        </ul>
        <div class="back-link">
            <a href="index.html">Back to Latest</a>
        </div>
    </div>
</body>
</html>
"""


def _get_tag_class(tag: str) -> str:
    """Get CSS class for tag."""
    tag_map = {
        "Short-term Surge": "tag-short-term-surge",
        "Long-term Growth": "tag-long-term-growth",
        "High Confidence": "tag-high-confidence",
        "Balanced": "tag-balanced",
        "Mixed": "tag-mixed",
    }
    return tag_map.get(tag, "tag-mixed")


def _format_value(value, col_name: str) -> str:
    """Format value for HTML display."""
    if pd.isna(value):
        return "-"

    if col_name == "rank":
        rank_class = f"rank-{int(value)}" if int(value) <= 3 else ""
        return f'<span class="rank {rank_class}">{int(value)}</span>'

    if col_name == "code":
        return f'<span class="code">{value}</span>'

    if col_name == "name":
        return f'<span class="name">{value}</span>'

    if col_name == "tag":
        tag_class = _get_tag_class(str(value))
        return f'<span class="tag {tag_class}">{value}</span>'

    if col_name == "current_price":
        return f'<span class="number">{int(value):,}</span>'

    if col_name in ["short_ret", "mid_ret", "long_ret"]:
        try:
            pct = float(value)
            css_class = "positive" if pct > 0 else "negative" if pct < 0 else ""
            sign = "+" if pct > 0 else ""
            return f'<span class="number {css_class}">{sign}{pct:.1f}%</span>'
        except (ValueError, TypeError):
            return str(value)

    if col_name == "agreement":
        try:
            val = float(value)
            return f'<span class="number">{val:.2f}</span>'
        except (ValueError, TypeError):
            return str(value)

    if col_name == "total_score":
        try:
            val = float(value)
            return f'<span class="number">{val:.4f}</span>'
        except (ValueError, TypeError):
            return str(value)

    if col_name == "freq_count":
        return f'<span class="number">{int(value)}</span>'

    return str(value)


def _df_to_html_table(df: pd.DataFrame) -> str:
    """Convert DataFrame to HTML table."""
    display_cols = [
        "rank", "code", "name", "current_price",
        "short_ret", "mid_ret", "long_ret",
        "agreement", "total_score", "tag", "freq_count"
    ]
    available_cols = [c for c in display_cols if c in df.columns]

    col_names = {
        "rank": "순위",
        "code": "코드",
        "name": "종목명",
        "current_price": "현재가",
        "short_ret": "Short Δ",
        "mid_ret": "Mid Δ",
        "long_ret": "Long Δ",
        "agreement": "Agreement",
        "total_score": "Score",
        "tag": "유형",
        "freq_count": "빈도",
    }

    html_parts = ["<table>", "<thead><tr>"]

    for col in available_cols:
        header = col_names.get(col, col)
        html_parts.append(f"<th>{header}</th>")

    html_parts.append("</tr></thead>")
    html_parts.append("<tbody>")

    for _, row in df.iterrows():
        html_parts.append("<tr>")
        for col in available_cols:
            value = row.get(col, "")
            formatted = _format_value(value, col)
            html_parts.append(f"<td>{formatted}</td>")
        html_parts.append("</tr>")

    html_parts.append("</tbody></table>")

    return "\n".join(html_parts)


class HTMLGenerator:
    """HTML page generator for ensemble results."""

    def __init__(
        self,
        pages_dir: Path | str | None = None,
        github_repo: str = "avantchoi82/chronosbolt-moirai-ttm",
    ):
        """Initialize generator.

        Args:
            pages_dir: Output directory for HTML files
            github_repo: GitHub repository name (owner/repo)
        """
        self.pages_dir = Path(pages_dir) if pages_dir else PAGES_DIR
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.github_repo = github_repo

    def generate(
        self,
        df: pd.DataFrame,
        as_of_date: date | None = None,
        top_n: int = 30,
        result_csv: str | None = None,
    ) -> dict[str, Path]:
        """Generate HTML pages.

        Args:
            df: Results DataFrame (from top30.csv)
            as_of_date: Date of results
            top_n: Number of top stocks
            result_csv: Filename of result CSV for download link

        Returns:
            Dictionary of generated file paths
        """
        paths = {}

        if as_of_date is None:
            as_of_date = date.today()

        date_str = as_of_date.strftime("%Y-%m-%d")
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Default result CSV filename
        if result_csv is None:
            result_csv = f"top30_{as_of_date.strftime('%Y_%m_%d')}.csv"

        # Generate table HTML
        top_n_table = _df_to_html_table(df.head(top_n))

        # Generate main page
        html_content = HTML_TEMPLATE.format(
            date_str=date_str,
            generated_at=generated_at,
            top_n=top_n,
            top_n_table=top_n_table,
            github_repo=self.github_repo,
            result_csv=result_csv,
        )

        # Save index.html
        index_path = self.pages_dir / "index.html"
        index_path.write_text(html_content, encoding="utf-8")
        paths["index"] = index_path

        # Save dated version
        dated_filename = f"result_{as_of_date.strftime('%Y_%m_%d')}.html"
        dated_path = self.pages_dir / dated_filename
        dated_path.write_text(html_content, encoding="utf-8")
        paths["dated"] = dated_path

        # Update history page
        history_path = self._update_history()
        paths["history"] = history_path

        logger.info(f"HTML pages generated: {index_path}")

        return paths

    def _update_history(self) -> Path:
        """Update history page."""
        result_files = sorted(
            self.pages_dir.glob("result_*.html"),
            reverse=True
        )

        history_items = []
        for f in result_files[:30]:
            date_part = f.stem.replace("result_", "")
            date_display = date_part.replace("_", "-")

            history_items.append(
                f'<li><a href="{f.name}">'
                f'<span class="date">{date_display}</span>'
                f'</a></li>'
            )

        html_content = HISTORY_TEMPLATE.format(
            history_items="\n".join(history_items)
        )

        history_path = self.pages_dir / "history.html"
        history_path.write_text(html_content, encoding="utf-8")

        return history_path


def generate_html_pages(
    df: pd.DataFrame,
    as_of_date: date | None = None,
    top_n: int = 30,
    pages_dir: Path | str | None = None,
    github_repo: str = "avantchoi82/chronosbolt-moirai-ttm",
    result_csv: str | None = None,
) -> dict[str, Path]:
    """Generate HTML pages (convenience function).

    Args:
        df: Results DataFrame
        as_of_date: Date of results
        top_n: Number of top stocks
        pages_dir: Output directory
        result_csv: Filename of result CSV for download link
        github_repo: GitHub repository name

    Returns:
        Dictionary of generated file paths
    """
    generator = HTMLGenerator(pages_dir, github_repo)
    return generator.generate(df, as_of_date, top_n, result_csv)
