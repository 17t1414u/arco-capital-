"""
sp500_universe.py — S&P500構成銘柄ユニバース管理

S&P500の全銘柄リストを取得・キャッシュする。
Wikipediaからの取得（無料）+ ローカルキャッシュで高速化。

使用例:
    tickers = get_sp500_tickers()
    print(f"S&P500: {len(tickers)}銘柄")
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# キャッシュファイルパス（週1回更新）
_CACHE_PATH = Path(__file__).parent.parent / "cache" / "sp500_tickers.json"
_CACHE_TTL_DAYS = 7


def get_sp500_tickers(force_refresh: bool = False) -> list[str]:
    """
    S&P500構成銘柄のティッカーリストを返す。
    キャッシュが7日以内ならキャッシュを使用、それ以外はWikipediaから取得。

    Args:
        force_refresh: True でキャッシュを無視して再取得

    Returns:
        list[str]: ティッカーシンボルのリスト（例: ["AAPL", "MSFT", ...]）
    """
    # キャッシュチェック
    if not force_refresh and _is_cache_valid():
        return _load_cache()

    # Wikipedia から取得を試みる
    try:
        tickers = _fetch_from_wikipedia()
        _save_cache(tickers)
        print(f"✅ S&P500リスト更新: {len(tickers)}銘柄 (Wikipedia)")
        return tickers
    except Exception as e:
        print(f"⚠️ Wikipedia取得失敗: {e} → フォールバックリストを使用")
        return _get_fallback_tickers()


def _is_cache_valid() -> bool:
    """キャッシュが有効期限内か確認する"""
    if not _CACHE_PATH.exists():
        return False
    try:
        data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(data["cached_at"])
        return datetime.now() - cached_at < timedelta(days=_CACHE_TTL_DAYS)
    except Exception:
        return False


def _load_cache() -> list[str]:
    """キャッシュからティッカーリストを読み込む"""
    data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    return data["tickers"]


def _save_cache(tickers: list[str]) -> None:
    """ティッカーリストをキャッシュに保存する"""
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(
        json.dumps({"cached_at": datetime.now().isoformat(), "tickers": tickers},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _fetch_from_wikipedia() -> list[str]:
    """WikipediaのS&P500一覧テーブルからティッカーを取得する"""
    import pandas as pd
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(url)
    df = tables[0]
    tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
    return sorted(tickers)


def _get_fallback_tickers() -> list[str]:
    """
    Wikipediaが取得できない場合のフォールバック。
    主要なS&P500構成銘柄100銘柄を返す。
    """
    return [
        # テクノロジー
        "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "META", "AVGO", "ORCL",
        "CSCO", "ADBE", "CRM", "AMD", "INTC", "QCOM", "TXN", "MU", "AMAT",
        "LRCX", "KLAC", "MRVL", "NOW", "SNOW", "PANW", "CRWD", "FTNT",
        # 通信
        "AMZN", "NFLX", "TMUS", "VZ", "T", "CHTR",
        # 金融
        "BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "C", "AXP",
        "BLK", "SCHW", "CB", "MMC", "AON", "ICE", "CME", "SPGI", "MCO",
        # ヘルスケア
        "UNH", "JNJ", "LLY", "ABT", "TMO", "MRK", "DHR", "ABBV", "PFE",
        "AMGN", "BMY", "GILD", "ISRG", "SYK", "MDT", "BSX", "EW", "ZBH",
        # 消費財（一般）
        "TSLA", "HD", "MCD", "NKE", "SBUX", "TGT", "LOW", "TJX", "BKNG",
        "MAR", "HLT", "GM", "F", "APTV", "TSCO",
        # 消費財（必需品）
        "PG", "KO", "PEP", "WMT", "COST", "MDLZ", "CL", "EL", "KHC",
        # エネルギー
        "XOM", "CVX", "COP", "EOG", "SLB", "PXD", "MPC", "VLO", "PSX",
        # 素材・工業
        "CAT", "DE", "HON", "UPS", "RTX", "BA", "LMT", "GE", "MMM",
        "EMR", "ETN", "PH", "ROK", "FTV", "IEX",
        # 不動産・公益
        "NEE", "DUK", "SO", "D", "AEP", "EXC", "XEL", "ES", "ETR",
    ]


def get_sp500_by_sector() -> dict[str, list[str]]:
    """
    S&P500銘柄をセクター別に返す（30%集中制限の管理用）。
    """
    try:
        import pandas as pd
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        df = pd.read_html(url)[0]
        df["Symbol"] = df["Symbol"].str.replace(".", "-", regex=False)
        sector_map: dict[str, list[str]] = {}
        for _, row in df.iterrows():
            sector = row.get("GICS Sector", "Unknown")
            ticker = row["Symbol"]
            sector_map.setdefault(sector, []).append(ticker)
        return sector_map
    except Exception:
        return {}
