"""
Natural language command parser for Telegram messages.

Converts user text like "/watch AAPL 170" into structured alert specs.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class AlertSpec:
    ticker: str
    condition_type: str   # 'price_below' | 'price_above' | 'rsi_below' | 'rsi_above'
    threshold: float
    raw: str


# Simple keyword → condition_type mapping
_CONDITION_MAP = {
    "below": "price_below",
    "under": "price_below",
    "drops below": "price_below",
    "above": "price_above",
    "over": "price_above",
    "rises above": "price_above",
    "rsi below": "rsi_below",
    "rsi above": "rsi_above",
    "rsi over": "rsi_above",
    "rsi under": "rsi_below",
}

# Regex: /watch <TICKER> <above|below> <NUMBER>
_WATCH_RE = re.compile(
    r"/watch\s+([A-Za-z]{1,5})\s+(above|below|over|under|rsi above|rsi below|rsi over|rsi under)\s+([\d.]+)",
    re.IGNORECASE,
)

# Simple: /watch AAPL 170  → infer "price_below" (price target)
_WATCH_SIMPLE_RE = re.compile(
    r"/watch\s+([A-Za-z]{1,5})\s+([\d.]+)",
    re.IGNORECASE,
)


def parse_watch_command(text: str) -> Optional[AlertSpec]:
    """
    Parse a /watch command into an AlertSpec.

    Examples:
      /watch AAPL below 170    → price_below @ 170
      /watch NVDA above 900    → price_above @ 900
      /watch TSLA rsi below 30 → rsi_below @ 30
      /watch MSFT 400          → price_below @ 400  (shorthand)
    """
    m = _WATCH_RE.search(text)
    if m:
        ticker = m.group(1).upper()
        keyword = m.group(2).lower()
        threshold = float(m.group(3))
        condition = _CONDITION_MAP.get(keyword, "price_below")
        return AlertSpec(ticker=ticker, condition_type=condition, threshold=threshold, raw=text)

    m = _WATCH_SIMPLE_RE.search(text)
    if m:
        ticker = m.group(1).upper()
        threshold = float(m.group(2))
        return AlertSpec(ticker=ticker, condition_type="price_below", threshold=threshold, raw=text)

    return None
