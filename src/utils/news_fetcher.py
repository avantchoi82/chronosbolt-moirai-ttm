"""News and Target Price Fetcher using Google News RSS.

Fetches stock news from Google News RSS and target prices from Naver Finance.
Supports parallel fetching for improved performance.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from datetime import datetime, timedelta
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("ensemble")

# Request headers to mimic browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Max parallel workers
MAX_WORKERS = 5


@dataclass
class StockNews:
    """Stock news data."""
    code: str
    name: str
    news_titles: list[str]
    target_prices: list[dict]  # [{"broker": "삼성증권", "price": 95000, "date": "2025.01.15"}]


def fetch_google_news(stock_name: str, max_news: int = 15) -> list[str]:
    """Fetch recent news titles from Google News RSS.

    Args:
        stock_name: Stock name in Korean (e.g., "삼성전자")
        max_news: Maximum number of news titles to fetch

    Returns:
        List of news titles
    """
    if not stock_name:
        return []

    try:
        encoded_name = urllib.parse.quote(stock_name)
        url = f"https://news.google.com/rss/search?q={encoded_name}&hl=ko&gl=KR&ceid=KR:ko"

        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "lxml-xml")
        items = soup.find_all("item")

        news_titles = []
        for item in items[:max_news]:
            title_tag = item.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)
                # Remove source suffix (e.g., " - 조선비즈")
                if " - " in title:
                    title = title.rsplit(" - ", 1)[0]
                news_titles.append(title)

        return news_titles

    except Exception as e:
        logger.warning(f"Failed to fetch news for {stock_name}: {e}")
        return []


def fetch_target_prices(code: str, max_items: int = 5) -> list[dict]:
    """Fetch analyst target prices from Naver Finance.

    Args:
        code: Stock code (e.g., "005930")
        max_items: Maximum number of target prices to fetch

    Returns:
        List of target price dictionaries
    """
    # Clean code
    code = code.split(".")[0].zfill(6)

    url = f"https://finance.naver.com/item/coinfo.naver?code={code}"

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        target_prices = []

        # Try to find consensus/target price info
        # Naver Finance shows this in the "투자의견" section
        consensus_url = f"https://finance.naver.com/item/coinfo.naver?code={code}&target=finsum_more"

        response2 = requests.get(consensus_url, headers=HEADERS, timeout=10)
        soup2 = BeautifulSoup(response2.text, "html.parser")

        # Look for target price table
        tables = soup2.select("table")
        for table in tables:
            rows = table.select("tr")
            for row in rows:
                cells = row.select("td")
                if len(cells) >= 3:
                    # Try to extract broker, target price, date
                    text = row.get_text()
                    # Simple pattern matching for prices
                    price_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*원', text)
                    if price_match and len(target_prices) < max_items:
                        try:
                            price = int(price_match.group(1).replace(",", ""))
                            broker = cells[0].get_text(strip=True) if cells else "증권사"
                            target_prices.append({
                                "broker": broker[:10],  # Truncate long names
                                "price": price,
                            })
                        except (ValueError, IndexError):
                            pass

        return target_prices

    except Exception as e:
        logger.warning(f"Failed to fetch target prices for {code}: {e}")
        return []


def fetch_stock_info(code: str, name: str = "", months: int = 2) -> StockNews:
    """Fetch all stock information (news + target prices).

    Args:
        code: Stock code
        name: Stock name (used for Google News search)
        months: Number of months to look back for news (not used with Google News)

    Returns:
        StockNews dataclass with all information
    """
    # Use Google News RSS with stock name
    news_titles = fetch_google_news(name, max_news=15)
    target_prices = fetch_target_prices(code)

    return StockNews(
        code=code,
        name=name,
        news_titles=news_titles,
        target_prices=target_prices,
    )


def fetch_multiple_stocks(stocks: list[tuple[str, str]], months: int = 2) -> list[StockNews]:
    """Fetch information for multiple stocks in parallel.

    Args:
        stocks: List of (code, name) tuples
        months: Number of months to look back

    Returns:
        List of StockNews objects (in same order as input)
    """
    results = [None] * len(stocks)

    def fetch_one(idx_code_name):
        idx, code, name = idx_code_name
        logger.info(f"[{idx+1}/{len(stocks)}] Fetching {name} ({code})...")
        return idx, fetch_stock_info(code, name, months)

    # Parallel fetch with ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(fetch_one, (idx, code, name))
            for idx, (code, name) in enumerate(stocks)
        ]

        for future in as_completed(futures):
            try:
                idx, info = future.result()
                results[idx] = info
            except Exception as e:
                logger.error(f"Fetch error: {e}")

    # Filter out None values (failed fetches)
    return [r for r in results if r is not None]


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)

    test_stocks = [
        ("005930", "삼성전자"),
        ("000660", "SK하이닉스"),
    ]

    for code, name in test_stocks:
        info = fetch_stock_info(code, name)
        print(f"\n=== {info.name} ({info.code}) ===")
        print(f"News ({len(info.news_titles)}):")
        for title in info.news_titles[:5]:
            print(f"  - {title}")
        print(f"Target Prices ({len(info.target_prices)}):")
        for tp in info.target_prices:
            print(f"  - {tp['broker']}: {tp['price']:,}원")
