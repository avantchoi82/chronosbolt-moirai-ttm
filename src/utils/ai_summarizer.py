"""AI Summarizer using Google Gemini API.

Generates stock news summaries and keywords using Gemini.
Includes retry logic for rate limiting.
"""

from __future__ import annotations

import logging
import os
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

import google.generativeai as genai

from .news_fetcher import StockNews

logger = logging.getLogger("ensemble")

# Retry settings for rate limit handling
MAX_RETRIES = 3
RETRY_DELAY = 5.0  # seconds between retries (exponential backoff)


@dataclass
class StockSummary:
    """AI-generated stock summary."""
    code: str
    name: str
    summary: str  # 100자 요약
    keywords: list[str]  # 7개 키워드
    target_prices: list[dict]  # 목표주가 정보


def _get_gemini_client():
    """Get configured Gemini client."""
    # Try reading from google.txt first, then environment variable
    api_key = None

    # Check for google.txt in project root
    google_txt = Path(__file__).parent.parent.parent / "google.txt"
    if google_txt.exists():
        api_key = google_txt.read_text(encoding="utf-8").strip()

    # Fallback to environment variable
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("No API key found (google.txt or GEMINI_API_KEY)")

    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-3-flash-preview")


def generate_summary(stock_info: StockNews) -> StockSummary:
    """Generate AI summary for a stock.

    Args:
        stock_info: StockNews object with news titles and target prices

    Returns:
        StockSummary with AI-generated summary and keywords
    """
    if not stock_info.news_titles:
        return StockSummary(
            code=stock_info.code,
            name=stock_info.name,
            summary="최근 뉴스 정보가 없습니다.",
            keywords=[],
            target_prices=stock_info.target_prices,
        )

    # Build prompt
    news_text = "\n".join([f"- {title}" for title in stock_info.news_titles[:15]])

    target_price_text = ""
    if stock_info.target_prices:
        tp_list = [f"{tp['broker']}: {tp['price']:,}원" for tp in stock_info.target_prices[:3]]
        target_price_text = f"\n\n증권사 목표주가: {', '.join(tp_list)}"

    prompt = f"""다음은 {stock_info.name}({stock_info.code})의 최근 뉴스 헤드라인입니다:

{news_text}{target_price_text}

위 뉴스를 바탕으로:
1. 100자 이내로 핵심 내용을 요약해주세요. (투자 관점에서 중요한 포인트 위주)
2. 관련 키워드 7개를 추출해주세요. (해시태그 형식 없이 단어만)

JSON 형식으로 응답해주세요:
{{"summary": "요약 내용", "keywords": ["키워드1", "키워드2", ...]}}
"""

    model = _get_gemini_client()

    for attempt in range(MAX_RETRIES):
        try:
            response = model.generate_content(prompt)

            # Parse response
            response_text = response.text.strip()

            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                summary = result.get("summary", "")[:150]  # Limit length
                keywords = result.get("keywords", [])[:7]  # Limit to 7

                return StockSummary(
                    code=stock_info.code,
                    name=stock_info.name,
                    summary=summary,
                    keywords=keywords,
                    target_prices=stock_info.target_prices,
                )
            else:
                logger.warning(f"Failed to parse Gemini response for {stock_info.code}")
                return StockSummary(
                    code=stock_info.code,
                    name=stock_info.name,
                    summary=response_text[:100],
                    keywords=[],
                    target_prices=stock_info.target_prices,
                )

        except Exception as e:
            error_str = str(e)
            # Check if rate limited (429 error)
            if "429" in error_str and attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY * (attempt + 1)
                logger.warning(f"Rate limited for {stock_info.code}, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue

            logger.error(f"Gemini API error for {stock_info.code}: {e}")
            return StockSummary(
                code=stock_info.code,
                name=stock_info.name,
                summary=f"AI 요약 생성 실패: {str(e)[:50]}",
                keywords=[],
                target_prices=stock_info.target_prices,
            )

    # If all retries failed
    return StockSummary(
        code=stock_info.code,
        name=stock_info.name,
        summary="AI 요약 생성 실패 (재시도 초과)",
        keywords=[],
        target_prices=stock_info.target_prices,
    )


def generate_summaries(stock_infos: list[StockNews]) -> list[StockSummary]:
    """Generate summaries for multiple stocks.

    Args:
        stock_infos: List of StockNews objects

    Returns:
        List of StockSummary objects
    """
    summaries = []

    for info in stock_infos:
        logger.info(f"Generating summary for {info.name} ({info.code})...")
        summary = generate_summary(info)
        summaries.append(summary)

    return summaries


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)

    from .news_fetcher import fetch_stock_info

    test_info = fetch_stock_info("005930", "삼성전자")
    print(f"\nNews titles: {len(test_info.news_titles)}")

    summary = generate_summary(test_info)
    print(f"\n=== {summary.name} Summary ===")
    print(f"Summary: {summary.summary}")
    print(f"Keywords: {', '.join(summary.keywords)}")
    print(f"Target Prices: {summary.target_prices}")
