"""
sp500_universe.py — S&P500構成銘柄ユニバース管理

S&P500の全銘柄リストを取得・キャッシュする。

取得ソースの優先順位:
  1. GitHub datahub CSV (primary) — lxml 不要、高速、CDN配信
  2. Wikipedia (secondary) — pandas.read_html + lxml 依存
  3. 埋め込みフォールバックリスト (tertiary)

使用例:
    tickers = get_sp500_tickers()
    print(f"S&P500: {len(tickers)}銘柄")
"""

import csv
import io
import json
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# キャッシュファイルパス（週1回更新）
_CACHE_PATH = Path(__file__).parent.parent / "cache" / "sp500_tickers.json"
_CACHE_TTL_DAYS = 7

# データソース URL
_DATAHUB_CSV_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/"
    "master/data/constituents.csv"
)
_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def get_sp500_tickers(force_refresh: bool = False) -> list[str]:
    """
    S&P500構成銘柄のティッカーリストを返す。
    キャッシュが7日以内ならキャッシュを使用、それ以外はオンラインから取得。

    Args:
        force_refresh: True でキャッシュを無視して再取得

    Returns:
        list[str]: ティッカーシンボルのリスト（例: ["AAPL", "MSFT", ...]）
    """
    # キャッシュチェック
    if not force_refresh and _is_cache_valid():
        return _load_cache()

    # 1次ソース: GitHub datahub CSV (高速・軽量、lxml 不要)
    try:
        tickers = _fetch_from_datahub()
        _save_cache(tickers)
        print(f"✅ S&P500リスト更新: {len(tickers)}銘柄 (datahub CSV)")
        return tickers
    except Exception as e:
        print(f"⚠️ datahub CSV 取得失敗: {e}")

    # 2次ソース: Wikipedia
    try:
        tickers = _fetch_from_wikipedia()
        _save_cache(tickers)
        print(f"✅ S&P500リスト更新: {len(tickers)}銘柄 (Wikipedia)")
        return tickers
    except Exception as e:
        print(f"⚠️ Wikipedia取得失敗: {e} → フォールバックリストを使用")

    # 3次ソース: 埋め込みフォールバック (最低125銘柄)
    return _get_fallback_tickers()


def _fetch_from_datahub() -> list[str]:
    """
    GitHub datahub リポジトリの S&P500 CSV からティッカーを取得する。

    - HTTPS 経由で CDN 配信 (高速、403 リスク低)
    - lxml 不要 (csv 標準ライブラリで処理)
    - 公開リポジトリ: github.com/datasets/s-and-p-500-companies
    """
    req = urllib.request.Request(
        _DATAHUB_CSV_URL,
        headers={"User-Agent": "ArcoCapital-Trading/1.0"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read().decode("utf-8")

    reader = csv.DictReader(io.StringIO(data))
    tickers = []
    for row in reader:
        symbol = (row.get("Symbol") or "").strip()
        if symbol:
            # Alpaca Data API v2 は BRK.B や BF.B のドット形式をそのまま受け付ける
            # （Yahoo Finance 形式の BRK-B は "invalid symbol" エラーになる）
            tickers.append(symbol)

    if len(tickers) < 400:
        raise RuntimeError(
            f"datahub CSV の行数が少なすぎます ({len(tickers)}銘柄)"
        )
    return sorted(tickers)


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
    datahub CSV の GICS Sector 列を利用する。
    """
    try:
        req = urllib.request.Request(
            _DATAHUB_CSV_URL,
            headers={"User-Agent": "ArcoCapital-Trading/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")

        reader = csv.DictReader(io.StringIO(data))
        sector_map: dict[str, list[str]] = {}
        for row in reader:
            symbol = (row.get("Symbol") or "").strip()
            sector = (row.get("GICS Sector") or "Unknown").strip()
            if symbol:
                sector_map.setdefault(sector, []).append(symbol)
        return sector_map
    except Exception:
        return {}
