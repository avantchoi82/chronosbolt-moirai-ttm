"""HTML Page Generator for GitHub Pages.

Generates HTML report pages from stock scanner source data.
Features left sidebar navigation with Stock/Macro tabs.
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
    <title>Stock Scanner - {date_str}</title>
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
            display: flex;
        }}

        /* Sidebar Navigation */
        .sidebar {{
            width: 80px;
            background: rgba(0, 0, 0, 0.3);
            border-right: 1px solid rgba(255, 255, 255, 0.1);
            position: fixed;
            top: 0;
            left: 0;
            height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding-top: 20px;
            z-index: 1000;
        }}
        .nav-btn {{
            width: 60px;
            height: 60px;
            border: none;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            color: #888;
            font-size: 0.7rem;
            cursor: pointer;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 4px;
            margin-bottom: 10px;
            transition: all 0.3s;
        }}
        .nav-btn:hover {{
            background: rgba(0, 212, 255, 0.2);
            color: #00d4ff;
        }}
        .nav-btn.active {{
            background: linear-gradient(135deg, #00d4ff 0%, #00ff88 100%);
            color: #1a1a2e;
        }}
        .nav-btn .icon {{
            font-size: 1.5rem;
        }}

        /* Main Content */
        .main-content {{
            margin-left: 80px;
            flex: 1;
            padding: 20px;
            width: calc(100% - 80px);
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        /* Tab Content */
        .tab-content {{
            display: none;
        }}
        .tab-content.active {{
            display: block;
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
        .date {{
            color: #888;
            font-size: 0.85rem;
        }}
        .pattern {{
            color: #ffd93d;
            font-weight: 500;
        }}
        .market {{
            color: #888;
            font-size: 0.85rem;
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
        .change-up {{
            color: #00ff88;
        }}
        .change-down {{
            color: #ff4757;
        }}
        .change-same {{
            color: #888;
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

        /* Macro tab specific styles */
        .macro-header {{
            background: linear-gradient(90deg, #ff6b6b, #ffd93d);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .macro-section .section-title {{
            color: #ffd93d;
            border-left-color: #ffd93d;
        }}
        .macro-section th {{
            background: rgba(255, 217, 61, 0.15);
            color: #ffd93d;
        }}
        .category {{
            font-weight: 600;
            color: #ffd93d;
        }}
        .fred-image-wrapper {{
            padding: 15px;
            text-align: center;
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
        }}
        .fred-image-wrapper img {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .fred-section .section-title {{
            color: #00d4ff;
            border-left-color: #00d4ff;
        }}

        /* Minute tab specific styles */
        .minute-header {{
            background: linear-gradient(90deg, #f97316, #facc15);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .minute-section .section-title {{
            color: #f97316;
            border-left-color: #f97316;
        }}
        .minute-section th {{
            background: rgba(249, 115, 22, 0.15);
            color: #f97316;
        }}

        /* ML tab specific styles */
        .ml-header {{
            background: linear-gradient(90deg, #a855f7, #06b6d4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .ml-section .section-title {{
            color: #a855f7;
            border-left-color: #a855f7;
        }}
        .ml-section th {{
            background: rgba(168, 85, 247, 0.15);
            color: #a855f7;
        }}
        .risk-flag {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.7rem;
            margin: 1px;
        }}
        .risk-high_vol {{
            background: rgba(255, 193, 7, 0.2);
            color: #ffc107;
        }}
        .risk-high_risk {{
            background: rgba(255, 71, 87, 0.2);
            color: #ff4757;
        }}
        .risk-low_volume {{
            background: rgba(108, 117, 125, 0.2);
            color: #6c757d;
        }}
        .risk-recent_drop {{
            background: rgba(255, 107, 107, 0.2);
            color: #ff6b6b;
        }}

        /* AI Summary row styles */
        .summary-row {{
            background: rgba(0, 212, 255, 0.05) !important;
        }}
        .summary-row:hover {{
            background: rgba(0, 212, 255, 0.08) !important;
        }}
        .summary-cell {{
            padding: 12px 15px !important;
            font-size: 0.85rem;
            line-height: 1.5;
        }}
        .summary-text {{
            color: #e4e4e4;
            margin-bottom: 8px;
        }}
        .summary-text .icon {{
            margin-right: 6px;
        }}
        .keywords {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-bottom: 8px;
        }}
        .keyword-tag {{
            background: rgba(0, 212, 255, 0.15);
            color: #00d4ff;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
        }}
        .target-prices {{
            color: #ffd93d;
            font-size: 0.8rem;
        }}
        .target-prices .icon {{
            margin-right: 6px;
        }}
        .target-price-item {{
            display: inline-block;
            margin-right: 12px;
        }}
    </style>
</head>
<body>
    <!-- Sidebar Navigation -->
    <nav class="sidebar">
        <button class="nav-btn active" onclick="showTab('stocks')" id="btn-stocks">
            <span class="icon">&#128200;</span>
            <span>&#51333;&#47785;</span>
        </button>
        <button class="nav-btn" onclick="showTab('minute')" id="btn-minute">
            <span class="icon">&#128338;</span>
            <span>&#48516;&#48393;</span>
        </button>
        <button class="nav-btn" onclick="showTab('ml')" id="btn-ml">
            <span class="icon">&#129302;</span>
            <span>ML</span>
        </button>
        <button class="nav-btn" onclick="showTab('macro')" id="btn-macro">
            <span class="icon">&#127760;</span>
            <span>&#47588;&#53356;&#47196;</span>
        </button>
    </nav>

    <!-- Main Content -->
    <div class="main-content">
        <div class="container">

            <!-- STOCKS TAB -->
            <div class="tab-content active" id="tab-stocks">
                <header>
                    <h1>Stock Scanner Source Data</h1>
                    <div class="subtitle">KOSPI &#49884;&#51109; + ChartKing + Real CAP + &#45800;&#49692;&#47784;&#47704;&#53568; | Top 20 Picks</div>
                    <div class="meta">
                        <span>Date: <strong>{date_str}</strong></span>
                        <span>|</span>
                        <span>Generated: <strong>{generated_at}</strong></span>
                    </div>
                </header>

                <div class="section">
                    <h2 class="section-title">&#128200; KOSPI &#49884;&#51109; &#49345;&#54889;</h2>
                    <div class="table-wrapper" style="padding: 20px; font-family: monospace; white-space: pre-line; line-height: 1.6;">
                        {kospidispart_content}
                    </div>
                </div>

                <div class="section">
                    <h2 class="section-title">&#127775; ChartKing (Best)</h2>
                    <div class="table-wrapper">
                        {chartking_table}
                    </div>
                </div>

                <div class="section">
                    <h2 class="section-title">&#128176; Real CAP (&#49884;&#44032;&#52509;&#50529; &#44592;&#51456;)</h2>
                    <div class="table-wrapper">
                        {real_cap_table}
                    </div>
                </div>

                <div class="section">
                    <h2 class="section-title">&#128640; &#45800;&#49692;&#47784;&#47704;&#53568; &#44592;&#48152;</h2>
                    <div class="table-wrapper">
                        {xgboost_table}
                    </div>
                </div>

                <div class="section">
                    <h2 class="section-title">Download Data</h2>
                    <div class="history-link" style="text-align: left; padding: 15px;">
                        <p style="margin-bottom: 10px; color: #888;">Source CSV Files:</p>
                        <a href="sources/" target="_blank">&#128193; Download Source CSVs</a>
                    </div>
                </div>
            </div>

            <!-- MINUTE TAB -->
            <div class="tab-content" id="tab-minute">
                <header>
                    <h1 class="minute-header">60&#48516;&#48393; &#49892;&#49884;&#44036; &#47784;&#47704;&#53568;</h1>
                    <div class="subtitle">Real Minute | 60-Minute Candle Momentum Scanner</div>
                    <div class="meta">
                        <span>Date: <strong>{date_str}</strong></span>
                        <span>|</span>
                        <span>Generated: <strong>{generated_at}</strong></span>
                    </div>
                </header>

                <div class="section minute-section">
                    <h2 class="section-title">&#128338; 60&#48516;&#48393; &#49345;&#49849;&#54056;&#53556;</h2>
                    <div class="table-wrapper">
                        {minute60_table}
                    </div>
                </div>

                <div class="section minute-section">
                    <h2 class="section-title">&#128202; &#51648;&#54364; &#49444;&#47749;</h2>
                    <div style="padding: 15px; color: #888;">
                        <p><strong>VAM:</strong> Volume Adjusted Momentum (&#44144;&#47000;&#47049; &#51312;&#51221; &#47784;&#47704;&#53568;)</p>
                        <p><strong>&#51060;&#44201;&#46020;:</strong> &#54788;&#51116;&#44032; &#45824;&#48708; &#51060;&#46041;&#54217;&#44512;&#49440; &#44340;&#47532;&#50984;</p>
                        <p><strong>&#44592;&#50872;&#44592;:</strong> &#52628;&#49464;&#49440; &#44592;&#50872;&#44592; (&#50577;&#49688;: &#49345;&#49849;, &#51020;&#49688;: &#54616;&#46973;)</p>
                    </div>
                </div>
            </div>

            <!-- ML TAB -->
            <div class="tab-content" id="tab-ml">
                <header>
                    <h1 class="ml-header">Machine Learning Stock Scanner</h1>
                    <div class="subtitle">LGBM | ML-based Stock Recommendations</div>
                    <div class="meta">
                        <span>Date: <strong>{date_str}</strong></span>
                        <span>|</span>
                        <span>Generated: <strong>{generated_at}</strong></span>
                    </div>
                </header>

                <div class="section ml-section">
                    <h2 class="section-title">&#129302; LGBM Top30 Recommendations</h2>
                    <div class="table-wrapper">
                        {lgbm_table}
                    </div>
                </div>
            </div>

            <!-- MACRO TAB -->
            <div class="tab-content" id="tab-macro">
                <header>
                    <h1 class="macro-header">ETF Sector Momentum Scanner</h1>
                    <div class="subtitle">ETFKing | Sector & Category Analysis</div>
                    <div class="meta">
                        <span>Date: <strong>{date_str}</strong></span>
                        <span>|</span>
                        <span>Generated: <strong>{generated_at}</strong></span>
                    </div>
                </header>

                <div class="section macro-section">
                    <h2 class="section-title">&#127482;&#127480; US ETF Sector Rankings</h2>
                    <div class="table-wrapper">
                        {macro_table}
                    </div>
                </div>

                <div class="section macro-section korea-section">
                    <h2 class="section-title">&#127472;&#127479; Korea ETF Sector Rankings</h2>
                    <div class="table-wrapper">
                        {korea_macro_table}
                    </div>
                </div>

                <div class="section macro-section fred-section">
                    <h2 class="section-title">&#128202; FRED Liquidity Dashboard (&#50976;&#46041;&#49457; &#45824;&#49884;&#48372;&#46300;)</h2>
                    <div class="fred-image-wrapper">
                        {fred_image}
                    </div>
                </div>

                <div class="section macro-section">
                    <h2 class="section-title">&#128200; Score Legend</h2>
                    <div style="padding: 15px; color: #888;">
                        <p><strong>Momentum Score:</strong> &#51333;&#54633; &#47784;&#47704;&#53568; &#51648;&#54364; (&#45458;&#51012;&#49688;&#47197; &#44053;&#54620; &#49345;&#49849; &#52628;&#49464;)</p>
                        <p><strong>Volatility Score:</strong> &#48320;&#46041;&#49457; &#51648;&#54364; (&#45230;&#51012;&#49688;&#47197; &#50504;&#51221;&#51201;)</p>
                        <p><strong>Composite Score:</strong> &#51333;&#54633; &#51216;&#49688; (&#47784;&#47704;&#53568;/&#48320;&#46041;&#49457; &#44256;&#47140;)</p>
                    </div>
                </div>
            </div>

            <footer>
                <p>Powered by ChartKing, Real & ETFKing</p>
                <div class="disclaimer">
                    &#9888;&#65039; &#53804;&#51088; &#52280;&#44256;&#50857; &#51088;&#47308;&#51077;&#45768;&#45796;. &#44284;&#44144; &#49457;&#44284;&#44032; &#48120;&#47000; &#49688;&#51061;&#51012; &#48372;&#51109;&#54616;&#51648; &#50506;&#49845;&#45768;&#45796;.
                    &#48516;&#49328;&#53804;&#51088;&#54616;&#44256; &#44048;&#45817; &#44032;&#45733;&#54620; &#48276;&#50948; &#45236;&#50640;&#49436; &#53804;&#51088;&#54616;&#49464;&#50836;.
                </div>
                <div class="history-link">
                    <a href="history.html">View History</a>
                    <a href="https://github.com/{github_repo}">GitHub</a>
                </div>
            </footer>
        </div>
    </div>

    <script>
        function showTab(tabName) {{
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {{
                tab.classList.remove('active');
            }});
            // Deactivate all buttons
            document.querySelectorAll('.nav-btn').forEach(btn => {{
                btn.classList.remove('active');
            }});
            // Show selected tab
            document.getElementById('tab-' + tabName).classList.add('active');
            document.getElementById('btn-' + tabName).classList.add('active');
        }}
    </script>
</body>
</html>
"""

HISTORY_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Scanner - History</title>
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
            <p>Stock Scanner Source Data</p>
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


def _extract_csv_comments(csv_path: Path) -> list[str]:
    """Extract comment lines from CSV file.

    Args:
        csv_path: Path to CSV file

    Returns:
        List of comment lines (without # prefix)
    """
    comments = []
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#"):
                    # Remove # and = decorations, clean up the line
                    cleaned = line.lstrip("#").strip()
                    if cleaned and not cleaned.startswith("="):
                        comments.append(cleaned)
                else:
                    break  # Stop at first non-comment line
    except Exception:
        pass
    return comments


def _source_df_to_html_table(
    df: pd.DataFrame,
    source: str,
    comments: list[str] | None = None,
    summaries: dict[str, "StockSummary"] | None = None,
) -> str:
    """Convert source DataFrame to HTML table.

    Args:
        df: Source DataFrame
        source: Source name (chartking, real)
        comments: Optional list of comment lines to display
        summaries: Optional dict of {stock_code: StockSummary} for top 10 stocks

    Returns:
        HTML table string
    """
    if df is None or df.empty:
        return '<p style="color: #888; padding: 20px;">No data available</p>'

    html_parts = []

    # Add comments section if available
    if comments:
        html_parts.append('<div class="csv-comments" style="padding: 10px 15px; margin-bottom: 10px; background: rgba(0, 212, 255, 0.1); border-radius: 8px; font-size: 0.85rem; color: #aaa;">')
        for comment in comments:
            html_parts.append(f'<div>{comment}</div>')
        html_parts.append('</div>')

    # Define columns and display names based on source
    if source == "chartking":
        # chartking: 티커, 종목명, 현재가, 신호가, 신호일, 매도예정, 모멘텀(%), 패턴, 손절가, 익절가
        display_cols = ["티커", "종목명", "현재가", "신호가", "신호일", "매도예정", "모멘텀(%)", "패턴", "손절가", "익절가"]
        col_names = {
            "티커": "코드",
            "종목명": "종목명",
            "현재가": "현재가",
            "신호가": "신호가",
            "신호일": "신호일",
            "매도예정": "매도예정",
            "모멘텀(%)": "모멘텀(%)",
            "패턴": "패턴",
            "손절가": "손절가",
            "익절가": "익절가",
        }
    elif source == "real":
        # real: 티커, 종목명, 현재가, 돌파가, 손절가, 익절가, VAM, 돌파일, 패턴, 사유, 시총(억), 이격도
        display_cols = ["티커", "종목명", "현재가", "돌파가", "손절가", "익절가", "VAM", "돌파일", "패턴", "사유", "시총(억)", "이격도"]
        col_names = {
            "티커": "코드",
            "종목명": "종목명",
            "현재가": "현재가",
            "돌파가": "돌파가",
            "손절가": "손절가",
            "익절가": "익절가",
            "VAM": "VAM",
            "돌파일": "돌파일",
            "패턴": "패턴",
            "사유": "사유",
            "시총(억)": "시총(억)",
            "이격도": "이격도",
        }
    elif source == "xgboost":
        # xgboost: rank, ticker, name, market, current_price, stop_loss_price, take_profit_price, momentum, score, market_cap
        display_cols = ["rank", "ticker", "name", "market", "current_price", "take_profit_price", "momentum", "score", "market_cap"]
        col_names = {
            "rank": "순위",
            "ticker": "코드",
            "name": "종목명",
            "market": "시장",
            "current_price": "현재가",
            "take_profit_price": "익절가",
            "momentum": "모멘텀",
            "score": "점수",
            "market_cap": "시총",
        }
    elif source == "lgbm":
        # lgbm: rank, ticker, name, score, score_percentile, market_cap, value_traded_20d, vol_20d, risk_flags
        display_cols = ["rank", "ticker", "name", "score", "score_percentile", "market_cap", "vol_20d", "risk_flags"]
        col_names = {
            "rank": "순위",
            "ticker": "코드",
            "name": "종목명",
            "score": "점수",
            "score_percentile": "백분위",
            "market_cap": "시총",
            "vol_20d": "변동성",
            "risk_flags": "리스크",
        }
    elif source == "minute60":
        # minute60: 티커, 종목명, 현재가, 손절가, 익절가, VAM, 이격도, 기울기, 사유, 시총(억)
        display_cols = ["티커", "종목명", "현재가", "손절가", "익절가", "VAM", "이격도", "기울기", "사유", "시총(억)"]
        col_names = {
            "티커": "코드",
            "종목명": "종목명",
            "현재가": "현재가",
            "손절가": "손절가",
            "익절가": "익절가",
            "VAM": "VAM",
            "이격도": "이격도",
            "기울기": "기울기",
            "사유": "패턴",
            "시총(억)": "시총(억)",
        }
    else:
        # Fallback: use all columns from DataFrame
        display_cols = list(df.columns)
        col_names = {c: c for c in display_cols}

    available_cols = [c for c in display_cols if c in df.columns]

    if not available_cols:
        # Fallback: show all columns
        available_cols = list(df.columns)
        col_names = {c: c for c in available_cols}

    # Start table
    html_parts.append("<table>")
    html_parts.append("<thead><tr>")
    html_parts.append("<th>#</th>")  # Rank column

    for col in available_cols:
        header = col_names.get(col, col)
        html_parts.append(f"<th>{header}</th>")

    html_parts.append("</tr></thead>")
    html_parts.append("<tbody>")

    # Determine which column contains the stock code
    code_col = None
    for col in ["티커", "ticker", "code"]:
        if col in df.columns:
            code_col = col
            break

    num_cols = len(available_cols) + 1  # +1 for rank column

    for idx, (_, row) in enumerate(df.head(20).iterrows(), 1):
        html_parts.append("<tr>")
        # Rank
        rank_class = f"rank-{idx}" if idx <= 3 else ""
        html_parts.append(f'<td><span class="rank {rank_class}">{idx}</span></td>')

        for col in available_cols:
            value = row.get(col, "")
            formatted = _format_source_value(value, col)
            html_parts.append(f"<td>{formatted}</td>")
        html_parts.append("</tr>")

        # Add summary row for top 10 stocks if summaries are provided
        if idx <= 10 and summaries and code_col:
            stock_code = str(row.get(code_col, "")).split(".")[0].zfill(6)
            summary = summaries.get(stock_code)
            if summary:
                html_parts.append(f'<tr class="summary-row">')
                html_parts.append(f'<td colspan="{num_cols}" class="summary-cell">')

                # Summary text
                html_parts.append(f'<div class="summary-text"><span class="icon">&#128240;</span>{summary.summary}</div>')

                # Keywords
                if summary.keywords:
                    html_parts.append('<div class="keywords">')
                    for kw in summary.keywords:
                        html_parts.append(f'<span class="keyword-tag">#{kw}</span>')
                    html_parts.append('</div>')

                # Target prices
                if summary.target_prices:
                    html_parts.append('<div class="target-prices"><span class="icon">&#127919;</span>')
                    for tp in summary.target_prices[:3]:
                        html_parts.append(f'<span class="target-price-item">{tp["broker"]}: {tp["price"]:,}원</span>')
                    html_parts.append('</div>')

                html_parts.append('</td>')
                html_parts.append('</tr>')

    html_parts.append("</tbody></table>")

    return "\n".join(html_parts)


def _format_source_value(value, col_name: str) -> str:
    """Format value for source table display."""
    if pd.isna(value) or value == "" or value == "nan":
        return "-"

    value_str = str(value)

    # Rank column
    if col_name == "rank":
        try:
            rank_val = int(float(value))
            rank_class = f"rank-{rank_val}" if rank_val <= 3 else ""
            return f'<span class="rank {rank_class}">{rank_val}</span>'
        except (ValueError, TypeError):
            return value_str

    # Code/Ticker columns
    if col_name in ["티커", "code", "ticker"]:
        # Remove .KS, .KQ suffix for cleaner display
        clean_code = value_str.split(".")[0]
        return f'<span class="code">{clean_code}</span>'

    # Name columns
    if col_name in ["종목명", "name"]:
        return f'<span class="name">{value_str}</span>'

    # Market column
    if col_name == "market":
        return f'<span class="market">{value_str}</span>'

    # Price columns (현재가, 신호가, 돌파가, 손절가, 익절가, current_price, take_profit_price)
    if col_name in ["현재가", "신호가", "돌파가", "손절가", "익절가", "close", "current_price", "take_profit_price", "stop_loss_price"]:
        try:
            price = float(value)
            return f'<span class="number">{int(price):,}</span>'
        except (ValueError, TypeError):
            return value_str

    # Percentage/Momentum columns
    if col_name in ["모멘텀(%)", "VAM", "등락률"]:
        try:
            pct = float(value_str.replace("%", "").replace(",", ""))
            css_class = "positive" if pct > 0 else "negative" if pct < 0 else ""
            sign = "+" if pct > 0 else ""
            return f'<span class="number {css_class}">{sign}{pct:.1f}%</span>'
        except (ValueError, TypeError):
            return value_str

    # XGBoost momentum (raw value, no %)
    if col_name == "momentum":
        try:
            val = float(value)
            css_class = "positive" if val > 0 else "negative" if val < 0 else ""
            return f'<span class="number {css_class}">{val:.1f}</span>'
        except (ValueError, TypeError):
            return value_str

    # Score column
    if col_name == "score":
        try:
            val = float(value)
            return f'<span class="number positive">{val:.4f}</span>'
        except (ValueError, TypeError):
            return value_str

    # Market cap column (시총(억) or market_cap)
    if col_name in ["시총(억)"]:
        try:
            cap = float(value_str.replace(",", ""))
            return f'<span class="number">{int(cap):,}</span>'
        except (ValueError, TypeError):
            return value_str

    # 이격도 column (disparity percentage)
    if col_name == "이격도":
        try:
            val = float(value_str.replace("%", "").replace(",", ""))
            return f'<span class="number">{val:.1f}%</span>'
        except (ValueError, TypeError):
            return value_str

    # 기울기 column (slope/trend)
    if col_name == "기울기":
        try:
            val = float(value)
            css_class = "positive" if val > 0 else "negative" if val < 0 else ""
            sign = "+" if val > 0 else ""
            return f'<span class="number {css_class}">{sign}{val:.2f}</span>'
        except (ValueError, TypeError):
            return value_str

    # Market cap in raw value (xgboost uses raw KRW)
    if col_name == "market_cap":
        try:
            cap = float(value)
            # Convert to 억원
            cap_억 = cap / 100_000_000
            return f'<span class="number">{int(cap_억):,}억</span>'
        except (ValueError, TypeError):
            return value_str

    # Date columns
    if col_name in ["신호일", "매도예정", "돌파일"]:
        return f'<span class="date">{value_str}</span>'

    # Pattern columns
    if col_name in ["패턴", "사유"]:
        return f'<span class="pattern">{value_str}</span>'

    # LGBM score_percentile column
    if col_name == "score_percentile":
        try:
            val = float(value)
            return f'<span class="number">{val:.1f}%</span>'
        except (ValueError, TypeError):
            return value_str

    # LGBM vol_20d column (volatility)
    if col_name == "vol_20d":
        try:
            val = float(value) * 100  # Convert to percentage
            css_class = "negative" if val > 5 else ""
            return f'<span class="number {css_class}">{val:.2f}%</span>'
        except (ValueError, TypeError):
            return value_str

    # LGBM risk_flags column
    if col_name == "risk_flags":
        try:
            # Parse risk flags from string like "['high_vol', 'low_volume']"
            flags_str = str(value).replace("[", "").replace("]", "").replace("'", "").replace('"', "")
            if not flags_str or flags_str == "":
                return '<span class="number">-</span>'
            flags = [f.strip() for f in flags_str.split(",") if f.strip()]
            if not flags:
                return '<span class="number">-</span>'
            html_flags = []
            for flag in flags:
                css_class = f"risk-{flag.replace(' ', '_')}"
                html_flags.append(f'<span class="risk-flag {css_class}">{flag}</span>')
            return " ".join(html_flags)
        except Exception:
            return value_str

    # Default: return as-is
    return value_str


def _macro_df_to_html_table(df: pd.DataFrame) -> str:
    """Convert macro (ETF) DataFrame to HTML table.

    Args:
        df: Macro DataFrame from etfking

    Returns:
        HTML table string
    """
    if df is None or df.empty:
        return '<p style="color: #888; padding: 20px;">No macro data available</p>'

    # Expected columns: date, rank, change, category, momentum_score, volatility_score, composite_score
    display_cols = ["rank", "change", "category", "momentum_score", "volatility_score", "composite_score"]
    available_cols = [c for c in display_cols if c in df.columns]

    col_names = {
        "rank": "순위",
        "change": "변동",
        "category": "섹터/카테고리",
        "momentum_score": "모멘텀",
        "volatility_score": "변동성",
        "composite_score": "종합점수",
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

            if col == "rank":
                rank_val = int(value) if pd.notna(value) else 0
                rank_class = f"rank-{rank_val}" if rank_val <= 3 else ""
                formatted = f'<span class="rank {rank_class}">{rank_val}</span>'
            elif col == "change":
                change_str = str(value)
                if "▲" in change_str:
                    formatted = f'<span class="change-up">{change_str}</span>'
                elif "▼" in change_str:
                    formatted = f'<span class="change-down">{change_str}</span>'
                else:
                    formatted = f'<span class="change-same">{change_str}</span>'
            elif col == "category":
                formatted = f'<span class="category">{value}</span>'
            elif col in ["momentum_score", "volatility_score"]:
                try:
                    val = float(value)
                    formatted = f'<span class="number">{val:.2f}</span>'
                except (ValueError, TypeError):
                    formatted = str(value)
            elif col == "composite_score":
                try:
                    val = float(value)
                    css_class = "positive" if val > 0 else "negative" if val < 0 else ""
                    sign = "+" if val > 0 else ""
                    formatted = f'<span class="number {css_class}">{sign}{val:.2f}</span>'
                except (ValueError, TypeError):
                    formatted = str(value)
            else:
                formatted = str(value) if pd.notna(value) else "-"

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
        source_csvs: dict[str, Path] | None = None,
        macro_csv: Path | None = None,
        korea_macro_csv: Path | None = None,
        xgboost_csv: Path | None = None,
        lgbm_csv: Path | None = None,
        fred_png: Path | None = None,
        stock_summaries: dict[str, dict] | None = None,
        kospidispart_txt: Path | None = None,
        real_cap_csv: Path | None = None,
        minute60_csv: Path | None = None,
    ) -> dict[str, Path]:
        """Generate HTML pages.

        Args:
            df: Results DataFrame (from top30.csv)
            as_of_date: Date of results
            top_n: Number of top stocks
            result_csv: Filename of result CSV for download link
            source_csvs: Dictionary of {source_name: csv_path}
            macro_csv: Path to US ETF macro CSV file
            korea_macro_csv: Path to Korea ETF macro CSV file
            xgboost_csv: Path to XGBoost CSV file
            lgbm_csv: Path to LGBM CSV file
            fred_png: Path to FRED liquidity dashboard PNG file
            stock_summaries: Dict of {source: {code: StockSummary}} for AI summaries
            kospidispart_txt: Path to KOSPIDISPART txt file (KOSPI market status)
            real_cap_csv: Path to Real CAP CSV file
            minute60_csv: Path to 60-minute candle CSV file

        Returns:
            Dictionary of generated file paths
        """
        paths = {}

        if as_of_date is None:
            as_of_date = date.today()

        date_str = as_of_date.strftime("%Y-%m-%d")
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Generate KOSPIDISPART content (KOSPI market status)
        kospidispart_content = '<p style="color: #888;">No KOSPI market status available</p>'
        if kospidispart_txt and kospidispart_txt.exists():
            try:
                content = kospidispart_txt.read_text(encoding="utf-8")
                # Format the content for HTML display
                kospidispart_content = content.replace("\n", "<br>")
            except Exception as e:
                logger.warning(f"Failed to read KOSPIDISPART txt: {e}")
                kospidispart_content = f'<p style="color: #888;">Error loading KOSPI market status: {e}</p>'

        # Generate Real CAP table
        real_cap_table = '<p style="color: #888; padding: 20px;">No Real CAP data available</p>'
        if real_cap_csv and real_cap_csv.exists():
            try:
                comments = _extract_csv_comments(real_cap_csv)
                real_cap_df = pd.read_csv(real_cap_csv, encoding="utf-8-sig", comment="#")
                real_cap_table = _source_df_to_html_table(real_cap_df, "real", comments, None)
            except Exception as e:
                logger.warning(f"Failed to read Real CAP CSV: {e}")
                real_cap_table = f'<p style="color: #888;">Error loading Real CAP data: {e}</p>'

        # Generate source tables (chartking only)
        source_tables = {"chartking": ""}
        if source_csvs:
            for source, csv_path in source_csvs.items():
                if source in source_tables and csv_path and csv_path.exists():
                    try:
                        # Extract comments from CSV
                        comments = _extract_csv_comments(csv_path)
                        source_df = pd.read_csv(csv_path, encoding="utf-8-sig", comment="#")
                        # Get summaries for this source if available
                        source_summ = stock_summaries.get(source, {}) if stock_summaries else None
                        source_tables[source] = _source_df_to_html_table(source_df, source, comments, source_summ)
                    except Exception as e:
                        logger.warning(f"Failed to read {source} CSV: {e}")
                        source_tables[source] = f'<p style="color: #888;">Error loading {source} data</p>'
                elif source in source_tables:
                    source_tables[source] = f'<p style="color: #888;">No {source} data available</p>'
        else:
            for source in source_tables:
                source_tables[source] = f'<p style="color: #888;">No {source} data available</p>'

        # Generate US macro table
        macro_table = '<p style="color: #888; padding: 20px;">No US ETF data available</p>'
        if macro_csv and macro_csv.exists():
            try:
                macro_df = pd.read_csv(macro_csv, encoding="utf-8-sig")
                macro_table = _macro_df_to_html_table(macro_df)
            except Exception as e:
                logger.warning(f"Failed to read US macro CSV: {e}")
                macro_table = f'<p style="color: #888;">Error loading US ETF data: {e}</p>'

        # Generate Korea macro table
        korea_macro_table = '<p style="color: #888; padding: 20px;">No Korea ETF data available</p>'
        if korea_macro_csv and korea_macro_csv.exists():
            try:
                korea_df = pd.read_csv(korea_macro_csv, encoding="utf-8-sig")
                korea_macro_table = _macro_df_to_html_table(korea_df)
            except Exception as e:
                logger.warning(f"Failed to read Korea macro CSV: {e}")
                korea_macro_table = f'<p style="color: #888;">Error loading Korea ETF data: {e}</p>'

        # Generate XGBoost table
        xgboost_table = '<p style="color: #888; padding: 20px;">No XGBoost data available</p>'
        if xgboost_csv and xgboost_csv.exists():
            try:
                xgboost_df = pd.read_csv(xgboost_csv, encoding="utf-8-sig")
                xgboost_summ = stock_summaries.get("xgboost", {}) if stock_summaries else None
                xgboost_table = _source_df_to_html_table(xgboost_df, "xgboost", None, xgboost_summ)
            except Exception as e:
                logger.warning(f"Failed to read XGBoost CSV: {e}")
                xgboost_table = f'<p style="color: #888;">Error loading XGBoost data: {e}</p>'

        # Generate LGBM table
        lgbm_table = '<p style="color: #888; padding: 20px;">No LGBM data available</p>'
        if lgbm_csv and lgbm_csv.exists():
            try:
                lgbm_comments = _extract_csv_comments(lgbm_csv)
                lgbm_df = pd.read_csv(lgbm_csv, encoding="utf-8-sig", comment="#")
                lgbm_table = _source_df_to_html_table(lgbm_df, "lgbm", lgbm_comments)
            except Exception as e:
                logger.warning(f"Failed to read LGBM CSV: {e}")
                lgbm_table = f'<p style="color: #888;">Error loading LGBM data: {e}</p>'

        # Generate Minute60 table
        minute60_table = '<p style="color: #888; padding: 20px;">No minute60 data available</p>'
        if minute60_csv and minute60_csv.exists():
            try:
                minute60_df = pd.read_csv(minute60_csv, encoding="utf-8-sig")
                minute60_table = _source_df_to_html_table(minute60_df, "minute60", None)
            except Exception as e:
                logger.warning(f"Failed to read Minute60 CSV: {e}")
                minute60_table = f'<p style="color: #888;">Error loading minute60 data: {e}</p>'

        # Generate FRED image HTML
        fred_image = '<p style="color: #888; padding: 20px;">No FRED liquidity dashboard available</p>'
        if fred_png and fred_png.exists():
            # Image will be copied to docs/images/fred_liquidity_dashboard.png
            fred_image = '<img src="images/fred_liquidity_dashboard.png" alt="FRED Liquidity Dashboard" />'

        # Generate main page
        html_content = HTML_TEMPLATE.format(
            date_str=date_str,
            generated_at=generated_at,
            github_repo=self.github_repo,
            kospidispart_content=kospidispart_content,
            real_cap_table=real_cap_table,
            chartking_table=source_tables["chartking"],
            xgboost_table=xgboost_table,
            lgbm_table=lgbm_table,
            macro_table=macro_table,
            korea_macro_table=korea_macro_table,
            fred_image=fred_image,
            minute60_table=minute60_table,
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
    source_csvs: dict[str, Path] | None = None,
    macro_csv: Path | None = None,
    korea_macro_csv: Path | None = None,
    xgboost_csv: Path | None = None,
    lgbm_csv: Path | None = None,
    fred_png: Path | None = None,
    stock_summaries: dict[str, dict] | None = None,
    kospidispart_txt: Path | None = None,
    real_cap_csv: Path | None = None,
    minute60_csv: Path | None = None,
) -> dict[str, Path]:
    """Generate HTML pages (convenience function).

    Args:
        df: Results DataFrame
        as_of_date: Date of results
        top_n: Number of top stocks
        pages_dir: Output directory
        result_csv: Filename of result CSV for download link
        github_repo: GitHub repository name
        source_csvs: Dictionary of {source_name: csv_path}
        macro_csv: Path to US ETF macro CSV file
        korea_macro_csv: Path to Korea ETF macro CSV file
        xgboost_csv: Path to XGBoost CSV file
        lgbm_csv: Path to LGBM CSV file
        fred_png: Path to FRED liquidity dashboard PNG file
        stock_summaries: Dict of {source: {code: StockSummary}} for AI summaries
        kospidispart_txt: Path to KOSPIDISPART txt file (KOSPI market status)
        real_cap_csv: Path to Real CAP CSV file
        minute60_csv: Path to 60-minute candle CSV file

    Returns:
        Dictionary of generated file paths
    """
    generator = HTMLGenerator(pages_dir, github_repo)
    return generator.generate(
        df, as_of_date, top_n, result_csv, source_csvs, macro_csv, korea_macro_csv,
        xgboost_csv, lgbm_csv, fred_png, stock_summaries, kospidispart_txt, real_cap_csv,
        minute60_csv
    )
