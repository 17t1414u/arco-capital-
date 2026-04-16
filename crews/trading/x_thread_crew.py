"""
XInvestmentThreadCrew — X投資スレッド自動投稿クルー（リアルデータ版）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【コンテンツ品質ルール】— 過去のフィードバックを永続化
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

■ 文章スタイル（絶対ルール）
  - 数字は「根拠」であり「見出し」ではない。冒頭から数字を羅列しない
  - 「なぜ？」「だから何？」を優先し、数字はその答えの補強に使う
  - 1投稿に数字は最大2〜3個。それ以上は言葉に置き換える
  - 友人に話しかけるように砕けた日本語で、でも内容は本質を突く
  - 自分の意見・判断として語る（「自分なら〜」「こう見てる」）
  - 不確かなことは「〜かもしれない」「〜の可能性が高い」と断言しない

■ データ整合性（絶対ルール）
  - 提供されていない数値を創作することは一切禁止
  - 使う数値はすべて提供済みの実データから引用（全部使う必要はない）
  - ニュースはAlpacaからではなく Yahoo Finance RSS / Reuters / MooMoo /
    Bloomberg などの公式ソースから取得する

■ 画像生成ルール
  - AI生成アート・インフォグラフィックは使用しない（Nano Banana廃止）
  - 全チャートはmatplotlib / mplfinanceで実データから生成する
  - ビジネス構造スライド（post2/post5）はマトリクス・テーブル形式
  - チャートのテキストは極力排除（タイトル・軸ラベル・凡例は最小限）
  - 文字化けは許容しない → Meiryo フォントを FontProperties で明示指定
  - チャートの時間軸は長く（6ヶ月）。ズームインしすぎない
  - x軸ラベルは月単位（YYYY/MM）、月が変わる最初の日のみ表示

■ チャート構成
  post1: ローソク足 + ボリンジャーバンド + 出来高（6ヶ月）
  post2: ビジネス構造スライド「変動要因3カラム分析」
  post3: ローソク足 + 出来高比較チャート（60日）
  post4: RSI + MACD テクニカル（60日・3パネル）
  post5: ビジネス構造スライド「トレード戦略マトリクス（テーブル）」

■ 5投稿の役割
  1. HOOK:   数字より「状況の面白さ」で引く。次が読みたくなる導入
  2. WHY:    ニュースを引用しつつ「つまりこういうこと」と噛み砕く
  3. HOW:    出来高・指標を「機関投資家が何をしていたか」視点で語る
  4. TA:     2つのシナリオ（強気/弱気）。数字は方向感の根拠に1〜2個だけ
  5. ACTION: 「自分ならこうする」という個人の判断として伝える

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

使用例:
    crew = XInvestmentThreadCrew(dry_run=True)   # 確認のみ
    crew = XInvestmentThreadCrew(dry_run=False)  # 本番投稿
    crew = XInvestmentThreadCrew(ticker="MU")    # 銘柄指定
"""

import io
import json
import os
import shutil
import tempfile
import time
from datetime import date, timedelta, datetime
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as _fm
import numpy as np

# Windows日本語フォント設定（メイリオ優先）
def _setup_jp_font() -> str:
    font_paths = [
        r"C:\Windows\Fonts\meiryo.ttc",
        r"C:\Windows\Fonts\YuGothM.ttc",
        r"C:\Windows\Fonts\msgothic.ttc",
        r"C:\Windows\Fonts\meiryob.ttc",
        r"C:\Windows\Fonts\yumin.ttf",
    ]
    for path in font_paths:
        try:
            from pathlib import Path as _Path
            if _Path(path).exists():
                _fm.fontManager.addfont(path)
                prop = _fm.FontProperties(fname=path)
                fname = prop.get_name()
                # フォントキャッシュを強制更新
                _fm.findfont(prop, rebuild_if_missing=True)
                matplotlib.rcParams["font.family"] = [fname, "sans-serif"]
                matplotlib.rcParams["font.sans-serif"] = [fname, "DejaVu Sans"]
                matplotlib.rcParams["axes.unicode_minus"] = False
                return fname
        except Exception:
            continue
    matplotlib.rcParams["axes.unicode_minus"] = False
    return ""

_JP_FONT = _setup_jp_font()

from config.settings import settings
# 統一フォーマット + 2026年Xアルゴリズム戦略: x_theme_crew.py とビジュアルを揃える
from crews.trading.x_theme_crew import (
    BOLD_INSIGHT,
    BOLD_DIGITS,
    THREAD_DIVIDER,
    format_post_text,
    ensure_discussion_question,
)

# ブランドカラー
BRAND_DARK  = "#0A0F1E"
BRAND_CYAN  = "#00D4FF"
BRAND_GOLD  = "#FFD700"
BRAND_WHITE = "#FFFFFF"
BRAND_RED   = "#FF4444"
BRAND_GREEN = "#00CC66"

HASHTAGS = "#米国株 #投資 #テクニカル分析 #株式投資 #資産運用"

# 監視銘柄リスト（スクリーニング対象）
WATCHLIST = [
    "NVDA", "AMD", "MU", "INTC", "AVGO", "QCOM", "TSM",
    "AAPL", "MSFT", "GOOGL", "META", "AMZN", "TSLA",
    "JPM", "BAC", "GS", "MS",
    "XOM", "CVX",
    "SPY", "QQQ",
]


class XInvestmentThreadCrew:
    """
    X投資スレッド自動投稿クルー（リアルデータ版）。

    Args:
        dry_run: True = 投稿せず確認のみ（デフォルト: True）
        ticker:  銘柄を手動指定（空文字 = 当日トップムーバーを自動選定）
    """

    def __init__(self, dry_run: bool = True, ticker: str = ""):
        self.dry_run = dry_run
        self.ticker = ticker.upper() if ticker else ""

    def run(self) -> str:
        today = date.today().strftime("%Y年%m月%d日")
        mode_str = "🔍 ドライラン（投稿なし）" if self.dry_run else "🚀 本番投稿モード"
        _print_header(f"XInvestmentThreadCrew 起動 — {today}")
        print(f"  モード: {mode_str}\n")

        # STEP 1: 対象銘柄を選定
        print("📊 STEP 1/5: 対象銘柄を選定中...\n")
        ticker, market_data = self._select_ticker()
        print(f"   → 対象銘柄: {ticker}\n")
        print(f"   → 終値: ${market_data['close']:.2f}  "
              f"変化率: {market_data['change_pct']:+.2f}%  "
              f"RSI: {market_data['rsi']:.1f}\n")

        # STEP 2: ニュース収集
        print("📰 STEP 2/5: ニュース収集中 (Alpaca News)...\n")
        news_items = self._fetch_news(ticker)
        print(f"   → {len(news_items)}件のニュースを取得\n")
        for n in news_items[:3]:
            print(f"   • {n['headline'][:70]}")
        print()

        # STEP 3: チャート生成
        print("📈 STEP 3/5: リアルチャート生成中 (mplfinance)...\n")
        chart_paths = self._generate_charts(ticker, market_data, news_items)
        print(f"   → {sum(1 for p in chart_paths if p)}枚のチャートを生成\n")

        # STEP 4: 台本生成
        print("✍️  STEP 4/5: 台本生成中 (Claude — 実データ使用)...\n")
        posts = self._generate_thread_scripts(ticker, market_data, news_items)
        _preview_posts(posts)

        # STEP 5: 投稿（またはドライラン）
        post_error = None
        if self.dry_run:
            print("📋 STEP 5/5: ドライランのため投稿をスキップします\n")
            thread_url = "（ドライラン）"
        else:
            print("🐦 STEP 5/5: X にスレッドを投稿中...\n")
            try:
                thread_url = self._post_thread(posts, chart_paths)
            except Exception as e:
                post_error = e
                thread_url = f"（投稿失敗: {e}）"
                print(f"⚠️  投稿失敗 — コンテンツは保存されます: {e}\n")

        # 結果保存
        saved_images = self._save_images(chart_paths, today)
        result = self._save_result(today, ticker, posts, thread_url, saved_images)
        _cleanup_images(chart_paths)

        _print_header("XInvestmentThreadCrew 完了")
        if post_error:
            print(f"  ⚠️ 投稿エラー: {post_error}")
        else:
            print(f"  スレッドURL: {thread_url}\n")

        if post_error:
            raise RuntimeError(f"X投稿失敗（コンテンツ保存済み）: {post_error}") from post_error
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: 対象銘柄選定
    # ─────────────────────────────────────────────────────────────────────────

    def _select_ticker(self) -> tuple[str, dict]:
        """
        手動指定された場合はそのデータを取得。
        未指定の場合は当日最大上昇率の銘柄を自動選定する。
        """
        if self.ticker:
            data = self._fetch_market_data(self.ticker)
            return self.ticker, data

        # 監視リストから当日トップムーバーを選定
        best_ticker = "SPY"
        best_data = self._fetch_market_data("SPY")
        best_abs_change = abs(best_data.get("change_pct", 0))

        for t in WATCHLIST:
            if t == "SPY":
                continue
            try:
                d = self._fetch_market_data(t)
                abs_change = abs(d.get("change_pct", 0))
                if abs_change > best_abs_change and d.get("volume", 0) > 1_000_000:
                    best_abs_change = abs_change
                    best_ticker = t
                    best_data = d
            except Exception:
                continue

        return best_ticker, best_data

    def _fetch_market_data(self, ticker: str) -> dict:
        """
        yfinance から実データを取得して指標を計算する。
        すべての数値は実データ。
        """
        import yfinance as yf

        stock = yf.Ticker(ticker)
        df = stock.history(period="6mo", interval="1d")
        if df.empty or len(df) < 20:
            raise ValueError(f"{ticker}: データ不足")

        close = float(df["Close"].iloc[-1])
        prev_close = float(df["Close"].iloc[-2])
        change_pct = (close - prev_close) / prev_close * 100
        volume = int(df["Volume"].iloc[-1])
        avg_volume_20 = int(df["Volume"].tail(20).mean())
        volume_ratio = volume / avg_volume_20 if avg_volume_20 > 0 else 1.0

        # RSI(14)
        delta = df["Close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss
        rsi_series = 100 - (100 / (1 + rs))
        rsi = float(rsi_series.iloc[-1])

        # SMA
        sma20 = float(df["Close"].rolling(20).mean().iloc[-1])
        sma50 = float(df["Close"].rolling(50).mean().iloc[-1]) if len(df) >= 50 else float("nan")

        # MACD(12,26,9)
        ema12 = df["Close"].ewm(span=12, adjust=False).mean()
        ema26 = df["Close"].ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line
        macd_val = float(macd_line.iloc[-1])
        signal_val = float(signal_line.iloc[-1])
        hist_val = float(histogram.iloc[-1])
        macd_crossed_bull = (float(histogram.iloc[-2]) < 0 and hist_val > 0)
        macd_crossed_bear = (float(histogram.iloc[-2]) > 0 and hist_val < 0)

        # ボリンジャーバンド(20,2)
        bb_mid = df["Close"].rolling(20).mean()
        bb_std = df["Close"].rolling(20).std()
        bb_upper = float((bb_mid + 2 * bb_std).iloc[-1])
        bb_lower = float((bb_mid - 2 * bb_std).iloc[-1])

        # 52週高値・安値
        df_1y = stock.history(period="1y", interval="1d")
        high_52w = float(df_1y["High"].max()) if not df_1y.empty else float("nan")
        low_52w  = float(df_1y["Low"].min())  if not df_1y.empty else float("nan")

        # 直近サポート・レジスタンス（直近20日の高値・安値）
        recent_high = float(df["High"].tail(20).max())
        recent_low  = float(df["Low"].tail(20).min())

        # 会社名・セクター
        info = {}
        try:
            info = stock.info
        except Exception:
            pass
        company_name = info.get("longName", ticker)
        sector = info.get("sector", "N/A")
        market_cap = info.get("marketCap", None)

        return {
            "ticker": ticker,
            "company_name": company_name,
            "sector": sector,
            "market_cap": market_cap,
            "close": close,
            "prev_close": prev_close,
            "change_pct": change_pct,
            "volume": volume,
            "avg_volume_20": avg_volume_20,
            "volume_ratio": volume_ratio,
            "rsi": rsi,
            "sma20": sma20,
            "sma50": sma50,
            "macd": macd_val,
            "macd_signal": signal_val,
            "macd_hist": hist_val,
            "macd_crossed_bull": macd_crossed_bull,
            "macd_crossed_bear": macd_crossed_bear,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "recent_high": recent_high,
            "recent_low": recent_low,
            "df": df,  # チャート生成用（保存しない）
        }

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: ニュース収集（Bloomberg / MooMoo / X / Reuters / Yahoo Finance）
    # ─────────────────────────────────────────────────────────────────────────

    def _fetch_news(self, ticker: str) -> list[dict]:
        """
        複数の公式ニュースソースから実際のニュースを収集する。
        優先順: Yahoo Finance → Reuters RSS → MooMoo → Bloomberg Markets → X検索
        すべて実ヘッドライン。架空のニュースは一切使用しない。
        """
        items: list[dict] = []
        seen: set[str] = set()

        def add_item(headline: str, summary: str, source: str, url: str = "") -> None:
            h = headline.strip()
            if h and h not in seen and len(h) > 10:
                seen.add(h)
                items.append({
                    "headline": h,
                    "summary": summary.strip()[:200],
                    "source": source,
                    "url": url,
                })

        # ── 1. Yahoo Finance（銘柄別ニュース） ─────────────────────────────
        try:
            import urllib.request
            import xml.etree.ElementTree as ET
            url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                tree = ET.parse(resp)
            for item in tree.iter("item"):
                title = item.findtext("title") or ""
                desc  = item.findtext("description") or ""
                link  = item.findtext("link") or ""
                add_item(title, desc, "Yahoo Finance", link)
        except Exception as e:
            print(f"   ⚠️ Yahoo Finance RSS エラー: {e}")

        # ── 2. Reuters Business RSS ────────────────────────────────────────
        if len(items) < 8:
            try:
                rss_feeds = [
                    "https://feeds.reuters.com/reuters/businessNews",
                    "https://feeds.reuters.com/reuters/technologyNews",
                ]
                for rss_url in rss_feeds:
                    req = urllib.request.Request(
                        rss_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        tree = ET.parse(resp)
                    for item in tree.iter("item"):
                        title = item.findtext("title") or ""
                        desc  = item.findtext("description") or ""
                        link  = item.findtext("link") or ""
                        # 銘柄名に関連するニュースを優先
                        if ticker in title.upper() or ticker in desc.upper():
                            add_item(title, desc, "Reuters", link)
            except Exception as e:
                print(f"   ⚠️ Reuters RSS エラー: {e}")

        # ── 3. MooMoo ニュースページ（スクレイピング） ─────────────────────
        if len(items) < 8:
            try:
                moo_url = f"https://www.moomoo.com/news/stock/{ticker.lower()}"
                req = urllib.request.Request(
                    moo_url, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                      "AppleWebKit/537.36",
                        "Accept-Language": "en-US,en;q=0.9",
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                # ニュースタイトルをhtmlから抽出（シンプルなパース）
                import re
                # MooMooのニュースタイトルは <a ...>タイトル</a> 形式
                titles = re.findall(
                    r'"title"\s*:\s*"([^"]{20,200})"', html)
                for t in titles[:8]:
                    t_clean = t.replace("\\u0027", "'").replace("\\n", " ")
                    add_item(t_clean, "", "MooMoo")
            except Exception as e:
                print(f"   ⚠️ MooMoo スクレイピング エラー: {e}")

        # ── 4. Bloomberg Markets ヘッドライン ──────────────────────────────
        if len(items) < 6:
            try:
                bb_url = "https://www.bloomberg.com/markets"
                req = urllib.request.Request(
                    bb_url, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                      "AppleWebKit/537.36",
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                import re
                # Bloombergのhreflang/headline パターン
                titles = re.findall(
                    r'<h[23][^>]*>\s*<a[^>]*>([^<]{20,150})</a>', html)
                for t in titles[:6]:
                    t_clean = re.sub(r'\s+', ' ', t).strip()
                    if t_clean:
                        add_item(t_clean, "", "Bloomberg")
            except Exception as e:
                print(f"   ⚠️ Bloomberg スクレイピング エラー: {e}")

        # ── 5. X（Twitter）検索 — 銘柄の最新ポスト ────────────────────────
        if len(items) < 6:
            try:
                # X API v2 search (無料版)
                import tweepy
                client_v2 = tweepy.Client(
                    bearer_token=settings.x_bearer_token,
                    wait_on_rate_limit=False,
                )
                query = f"${ticker} lang:ja -is:retweet"
                response = client_v2.search_recent_tweets(
                    query=query,
                    max_results=10,
                    tweet_fields=["text", "created_at", "author_id"],
                )
                if response.data:
                    for tweet in response.data[:5]:
                        text = tweet.text.replace("\n", " ")[:100]
                        add_item(f"[X] {text}", "", "X (Twitter)")
            except Exception as e:
                print(f"   ⚠️ X検索 エラー: {e}")

        # ── 6. yfinance フォールバック ──────────────────────────────────────
        if len(items) < 3:
            try:
                import yfinance as yf
                stock = yf.Ticker(ticker)
                yf_news = stock.news or []
                for n in yf_news[:8]:
                    title = n.get("title", "")
                    add_item(title, n.get("summary", ""), "Yahoo Finance",
                             n.get("link", ""))
            except Exception as e:
                print(f"   ⚠️ yfinance ニュース エラー: {e}")

        return items

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: チャート生成（実データ使用）
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_charts(
        self, ticker: str, market_data: dict, news_items: list[dict]
    ) -> list[Optional[str]]:
        """
        実データからチャートを5枚生成する。
        全て実データ／構造化ビジネスグラフィック。
        投稿1: ローソク足+BB（6ヶ月）
        投稿2: ビジネス構造スライド「変動要因分析」
        投稿3: 出来高分析チャート（60日）
        投稿4: RSI+MACDテクニカル（60日）
        投稿5: ビジネス構造スライド「トレード戦略マトリクス」
        """
        df = market_data["df"]
        paths: list[Optional[str]] = []

        # 投稿1: ローソク足 + BB + 出来高（6ヶ月）
        print("   📊 chart1: ローソク足+BB（6ヶ月）...")
        paths.append(self._chart_candle_bb(ticker, df, market_data))

        # 投稿2: ビジネス構造スライド「変動要因分析」
        print("   📊 chart2: ビジネス構造スライド（変動要因）...")
        paths.append(self._chart_business_why(ticker, market_data, news_items))

        # 投稿3: 出来高分析チャート（60日）
        print("   📊 chart3: 出来高分析チャート（60日）...")
        paths.append(self._chart_volume_analysis(ticker, df, market_data))

        # 投稿4: RSI+MACDテクニカル（60日）
        print("   📊 chart4: RSI+MACDテクニカル...")
        paths.append(self._chart_technical(ticker, df, market_data))

        # 投稿5: ビジネス構造スライド「トレード戦略マトリクス」
        print("   📊 chart5: ビジネス構造スライド（戦略マトリクス）...")
        paths.append(self._chart_business_strategy(ticker, market_data))

        return paths

    def _chart_candle_bb(self, ticker: str, df, market_data: dict) -> Optional[str]:
        """ローソク足 + ボリンジャーバンド + 出来高チャート"""
        try:
            import mplfinance as mpf

            n_days = min(126, len(df))  # 最大6ヶ月（約126取引日）
            df60 = df.tail(n_days).copy()

            # ボリンジャーバンド
            bb_mid = df["Close"].rolling(20).mean().tail(n_days)
            bb_std = df["Close"].rolling(20).std().tail(n_days)
            bb_upper = bb_mid + 2 * bb_std
            bb_lower = bb_mid - 2 * bb_std
            sma20 = df["Close"].rolling(20).mean().tail(n_days)
            sma50 = df["Close"].rolling(50).mean().tail(n_days)

            apds = [
                mpf.make_addplot(bb_upper, color=BRAND_CYAN, linestyle="--",
                                 width=0.8),
                mpf.make_addplot(bb_mid, color=BRAND_GOLD, linestyle="-",
                                 width=0.8),
                mpf.make_addplot(bb_lower, color=BRAND_CYAN, linestyle="--",
                                 width=0.8),
            ]
            if not sma50.isna().all():
                apds.append(
                    mpf.make_addplot(sma50, color="#FF8C00", linestyle="-",
                                     width=1.0)
                )

            style = mpf.make_mpf_style(
                base_mpf_style="nightclouds",
                facecolor=BRAND_DARK,
                edgecolor="#333344",
                figcolor=BRAND_DARK,
                gridcolor="#1A2030",
                gridstyle="--",
                gridaxis="both",
                marketcolors=mpf.make_marketcolors(
                    up=BRAND_GREEN, down=BRAND_RED,
                    edge="inherit", wick="inherit",
                    volume={"up": BRAND_GREEN, "down": BRAND_RED},
                ),
            )

            tmp = tempfile.NamedTemporaryFile(suffix=f"_{ticker}_chart1.png", delete=False)
            tmp.close()
            fig, axes = mpf.plot(
                df60,
                type="candle",
                volume=True,
                addplot=apds,
                style=style,
                figsize=(12, 7),
                returnfig=True,
                tight_layout=True,
                axisoff=False,
            )
            # 軸ラベル・タイトルを非表示
            for ax in fig.axes:
                ax.set_ylabel("")
                ax.set_xlabel("")
            fig.savefig(tmp.name, dpi=150, facecolor=BRAND_DARK, bbox_inches="tight")
            plt.close(fig)
            return tmp.name

        except Exception as e:
            print(f"      ⚠️ chart1 生成エラー: {e}")
            return None

    def _chart_volume_analysis(self, ticker: str, df, market_data: dict) -> Optional[str]:
        """出来高分析チャート（60日・20日平均比較）"""
        try:
            n = min(60, len(df))
            df_n = df.tail(n).copy()
            avg_vol = df["Volume"].rolling(20).mean().tail(n)

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7),
                                            gridspec_kw={"height_ratios": [3, 1]},
                                            facecolor=BRAND_DARK)
            fig.subplots_adjust(hspace=0.05)

            dates = df_n.index
            x = np.arange(len(dates))

            # ローソク足
            for i, (idx, row) in enumerate(df_n.iterrows()):
                color = BRAND_GREEN if row["Close"] >= row["Open"] else BRAND_RED
                ax1.plot([i, i], [row["Low"], row["High"]], color=color, linewidth=0.8)
                ax1.bar(i, abs(row["Close"] - row["Open"]),
                        bottom=min(row["Open"], row["Close"]),
                        color=color, width=0.7, alpha=0.85)

            # SMA20
            sma20 = df["Close"].rolling(20).mean().tail(n)
            ax1.plot(x, sma20.values, color=BRAND_GOLD, linewidth=1.0, linestyle="--")
            ax1.set_facecolor(BRAND_DARK)
            ax1.tick_params(colors=BRAND_WHITE, labelbottom=False, labelsize=8)
            ax1.set_ylabel("")
            ax1.set_xlabel("")
            ax1.spines[:].set_color("#333344")
            ax1.grid(color="#1A2030", linestyle="--", alpha=0.5)

            # 出来高バー（x軸に日付を表示）
            vol_colors = [BRAND_GREEN if df_n["Close"].iloc[i] >= df_n["Open"].iloc[i]
                          else BRAND_RED for i in range(len(df_n))]
            ax2.bar(x, df_n["Volume"].values, color=vol_colors, alpha=0.8, width=0.7)
            ax2.plot(x, avg_vol.values, color=BRAND_GOLD, linewidth=1.0, linestyle="--")
            ax2.set_facecolor(BRAND_DARK)
            ax2.set_ylabel("")
            ax2.set_xlabel("")
            # x軸: 月が変わった最初の日のみ表示（重複防止）
            seen_months2, tick_positions = set(), []
            for i, d in enumerate(dates):
                if hasattr(d, 'month') and d.month not in seen_months2:
                    seen_months2.add(d.month)
                    tick_positions.append(i)
            tick_labels = [dates[i].strftime("%Y/%m") for i in tick_positions]
            ax2.set_xticks(tick_positions)
            ax2.set_xticklabels(tick_labels, rotation=0, ha='center',
                                color=BRAND_WHITE, fontsize=8)
            ax2.tick_params(colors=BRAND_WHITE, labelsize=8)
            ax2.yaxis.set_major_formatter(
                matplotlib.ticker.FuncFormatter(lambda v, _: f"{v/1e6:.0f}M"))
            ax2.spines[:].set_color("#333344")
            ax2.grid(color="#1A2030", linestyle="--", alpha=0.5)

            tmp = tempfile.NamedTemporaryFile(suffix=f"_{ticker}_chart3.png", delete=False)
            tmp.close()
            fig.savefig(tmp.name, dpi=150, facecolor=BRAND_DARK, bbox_inches="tight")
            plt.close(fig)
            return tmp.name

        except Exception as e:
            print(f"      ⚠️ chart3 生成エラー: {e}")
            return None

    def _chart_technical(self, ticker: str, df, market_data: dict) -> Optional[str]:
        """RSI + MACD テクニカル指標チャート"""
        try:
            n = 60
            df60 = df.tail(n).copy()
            close = df["Close"]

            # RSI(14)
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rsi = (100 - 100 / (1 + gain / loss)).tail(n)

            # MACD
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd  = (ema12 - ema26).tail(n)
            sig   = macd.ewm(span=9, adjust=False).mean()
            hist  = (macd - sig).tail(n)

            fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 8),
                                                  gridspec_kw={"height_ratios": [3, 1.2, 1.5]},
                                                  facecolor=BRAND_DARK)
            fig.subplots_adjust(hspace=0.08)
            x = np.arange(n)

            # ローソク足
            for i, (idx, row) in enumerate(df60.iterrows()):
                color = BRAND_GREEN if row["Close"] >= row["Open"] else BRAND_RED
                ax1.plot([i, i], [row["Low"], row["High"]], color=color, linewidth=0.8)
                ax1.bar(i, abs(row["Close"] - row["Open"]),
                        bottom=min(row["Open"], row["Close"]),
                        color=color, width=0.7, alpha=0.85)

            ax1.set_facecolor(BRAND_DARK)
            ax1.set_ylabel("")
            ax1.set_xlabel("")
            ax1.tick_params(colors=BRAND_WHITE, labelbottom=False, labelsize=8)
            ax1.spines[:].set_color("#333344")
            ax1.grid(color="#1A2030", linestyle="--", alpha=0.4)

            # RSI
            ax2.plot(x, rsi.values, color=BRAND_CYAN, linewidth=1.2)
            ax2.axhline(70, color=BRAND_RED, linestyle="--", linewidth=0.8, alpha=0.7)
            ax2.axhline(30, color=BRAND_GREEN, linestyle="--", linewidth=0.8, alpha=0.7)
            ax2.fill_between(x, rsi.values, 70,
                             where=(rsi.values >= 70), color=BRAND_RED, alpha=0.2)
            ax2.fill_between(x, rsi.values, 30,
                             where=(rsi.values <= 30), color=BRAND_GREEN, alpha=0.2)
            ax2.set_ylim(0, 100)
            ax2.set_facecolor(BRAND_DARK)
            ax2.set_ylabel("RSI", color=BRAND_WHITE, fontsize=8)
            ax2.set_xlabel("")
            ax2.tick_params(colors=BRAND_WHITE, labelbottom=False, labelsize=7)
            ax2.spines[:].set_color("#333344")
            ax2.grid(color="#1A2030", linestyle="--", alpha=0.4)

            # MACD
            hist_colors = [BRAND_GREEN if v > 0 else BRAND_RED for v in hist.values]
            ax3.bar(x, hist.values, color=hist_colors, alpha=0.7, width=0.7)
            ax3.plot(x, macd.values, color=BRAND_CYAN, linewidth=1.0)
            ax3.plot(x, sig.values,  color=BRAND_GOLD, linewidth=1.0)
            ax3.axhline(0, color="#555566", linewidth=0.5)
            ax3.set_facecolor(BRAND_DARK)
            ax3.set_ylabel("MACD", color=BRAND_WHITE, fontsize=8)
            ax3.set_xlabel("")
            ax3.spines[:].set_color("#333344")
            ax3.grid(color="#1A2030", linestyle="--", alpha=0.4)
            # x軸: 月が変わった最初の日のみ表示（重複防止）
            dates60 = df60.index
            seen_months, tick_pos = set(), []
            for i, d in enumerate(dates60):
                if hasattr(d, 'month') and d.month not in seen_months:
                    seen_months.add(d.month)
                    tick_pos.append(i)
            ax3.set_xticks(tick_pos)
            ax3.set_xticklabels(
                [dates60[i].strftime("%Y/%m") for i in tick_pos],
                rotation=0, ha='center', color=BRAND_WHITE, fontsize=8
            )
            ax3.tick_params(colors=BRAND_WHITE, labelsize=8)

            tmp = tempfile.NamedTemporaryFile(suffix=f"_{ticker}_chart4.png", delete=False)
            tmp.close()
            fig.savefig(tmp.name, dpi=150, facecolor=BRAND_DARK, bbox_inches="tight")
            plt.close(fig)
            return tmp.name

        except Exception as e:
            print(f"      ⚠️ chart4 生成エラー: {e}")
            return None

    def _generate_nano_banana_image(self, idx: int, ticker: str, prompt: str) -> Optional[str]:
        """Nano Banana Pro (gemini) でブランドカラー画像を生成"""
        try:
            from google import genai
            from google.genai import types

            api_key = os.getenv("GOOGLE_API_KEY", "")
            if not api_key:
                return None

            client = genai.Client(api_key=api_key)
            full_prompt = (
                f"{prompt}. "
                f"Style: cinematic premium financial art, photorealistic. "
                f"Background: dark navy deep space ({BRAND_DARK}). "
                f"Accent colors: electric cyan ({BRAND_CYAN}), gold ({BRAND_GOLD}). "
                "CRITICAL: absolutely NO text, NO words, NO letters, NO numbers, "
                "NO labels, NO captions anywhere in the image. Pure visual only. "
                "16:9 aspect ratio, ultra high quality."
            )

            response = client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"]
                ),
            )
            for part in response.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    image_data = part.inline_data.data
                    if isinstance(image_data, str):
                        import base64
                        image_data = base64.b64decode(image_data)
                    tmp = tempfile.NamedTemporaryFile(
                        suffix=f"_{ticker}_chart{idx}.png", delete=False)
                    tmp.write(image_data)
                    tmp.close()
                    return tmp.name
            return None
        except Exception as e:
            print(f"      ⚠️ Nano Banana エラー (post {idx}): {e}")
            return None

    def _build_why_summaries(
        self, ticker: str, market_data: dict, news_items: list[dict]
    ) -> list[dict]:
        """
        Claude Haiku を使って英語ニュースから3視点の日本語要約を生成する。
        角度: 主因 / 背景 / 補足（テクニカル）
        戻り値: [{"angle": "主因", "summary": "...", "source": "..."}, ...]
        """
        import anthropic
        news_text = "\n".join(
            f"- [{n['source']}] {n['headline']}" for n in news_items[:12]
        )
        chg = market_data["change_pct"]
        direction = "上昇" if chg >= 0 else "下落"

        prompt = f"""${ticker} が本日{chg:+.1f}%{direction}しました。
以下のニュース・データをもとに、3つの異なる視点で日本語の要約を作成してください。

ニュース:
{news_text}

テクニカルデータ:
- RSI: {market_data['rsi']:.0f}
- 出来高: 20日平均比 {market_data['volume_ratio']:.1f}x
- SMA20: ${market_data['sma20']:.0f}

以下のJSON形式のみで返してください（説明不要）:
[
  {{"angle": "主因", "summary": "直接のトリガーを15字以内の日本語で", "source": "情報源名（英語可）"}},
  {{"angle": "背景", "summary": "市場・セクターの文脈を15字以内の日本語で", "source": "情報源名（英語可）"}},
  {{"angle": "テクニカル", "summary": "チャート・出来高の状況を15字以内の日本語で", "source": "テクニカル分析"}}
]"""

        try:
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            msg = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            return json.loads(raw)
        except Exception as e:
            print(f"      ⚠️ WHY要約生成エラー: {e}")
            # フォールバック: 生ニュースをそのまま使用
            fallback = []
            for i, label in enumerate(["主因", "背景", "補足"]):
                n = news_items[i] if i < len(news_items) else {"headline": "—", "source": ""}
                fallback.append({
                    "angle": label,
                    "summary": n["headline"][:30],
                    "source": n.get("source", ""),
                })
            return fallback

    def _chart_business_why(
        self, ticker: str, market_data: dict, news_items: list[dict]
    ) -> Optional[str]:
        """
        ビジネス構造スライド: 変動要因分析（3カラムマトリクス）
        ニュースをClaude Haikuで日本語3視点サマリーに変換して表示。
        """
        try:
            from matplotlib.font_manager import FontProperties
            fp = FontProperties(family=_JP_FONT) if _JP_FONT else None

            # Claude Haiku で日本語3視点要約を生成
            summaries = self._build_why_summaries(ticker, market_data, news_items)

            def t(ax, x, y, s, **kw):
                kw.setdefault("color", BRAND_WHITE)
                kw.setdefault("va", "center")
                if fp:
                    kw["fontproperties"] = fp
                ax.text(x, y, s, **kw)

            fig, ax = plt.subplots(figsize=(12, 7), facecolor=BRAND_DARK)
            ax.set_facecolor(BRAND_DARK)
            ax.set_xlim(0, 12)
            ax.set_ylim(0, 10)
            ax.axis("off")

            chg = market_data["change_pct"]
            arrow = "▲" if chg >= 0 else "▼"
            chg_color = BRAND_GREEN if chg >= 0 else BRAND_RED

            # ── ヘッダー ───────────────────────────────────────────────
            t(ax, 6, 9.4, f"${ticker}  変動要因分析",
              ha="center", fontsize=17, fontweight="bold", color=BRAND_CYAN)
            t(ax, 6, 8.85,
              f"本日: {arrow}{abs(chg):.1f}%  ─  "
              f"RSI {market_data['rsi']:.0f}  ─  "
              f"出来高 {market_data['volume_ratio']:.1f}x（20日平均比）",
              ha="center", fontsize=10, color="#AABBCC")
            ax.axhline(8.5, color=BRAND_CYAN, linewidth=0.8,
                       alpha=0.4, xmin=0.02, xmax=0.98)

            # ── 3カラムボックス ────────────────────────────────────────
            col_colors = [chg_color, "#FF8C00", BRAND_CYAN]
            box_left   = [0.25, 4.25, 8.25]

            for col, (bl, item) in enumerate(zip(box_left, summaries)):
                bw, bh = 3.5, 5.5
                by = 2.2
                angle   = item.get("angle", "")
                summary = item.get("summary", "")
                source  = item.get("source", "")[:18]

                # ボックス枠
                ax.add_patch(plt.Rectangle(
                    (bl, by), bw, bh,
                    facecolor="#0D1525", edgecolor=col_colors[col],
                    linewidth=1.8, zorder=2
                ))
                # ラベルバッジ
                ax.add_patch(plt.Rectangle(
                    (bl, by + bh - 0.7), bw, 0.7,
                    facecolor=col_colors[col], zorder=3
                ))
                t(ax, bl + bw / 2, by + bh - 0.35, angle,
                  ha="center", fontsize=11, fontweight="bold",
                  color=BRAND_DARK, zorder=4)

                # ソース（最初の単語だけ表示）
                src_short = source.split(" - ")[0].split("/")[0].strip()[:14]
                t(ax, bl + 0.2, by + bh - 1.15, f"[ {src_short} ]",
                  fontsize=8, color="#8899AA")

                # 日本語サマリー（14文字で折り返し、最大3行）
                lines = [summary[i:i+14] for i in range(0, len(summary), 14)]
                for li, line in enumerate(lines[:3]):
                    t(ax, bl + 0.25, by + bh - 1.95 - li * 1.1,
                      line, fontsize=12, color=BRAND_WHITE)

            # ── フッター ───────────────────────────────────────────────
            # 使用されたソース一覧を収集
            used_sources = list(dict.fromkeys(
                s.get("source", "") for s in summaries if s.get("source")
            ))
            sources_str = " / ".join(used_sources) if used_sources else "Yahoo Finance / Reuters / Bloomberg"
            ax.axhline(1.9, color="#2A3040", linewidth=0.5, xmin=0.02, xmax=0.98)
            t(ax, 6, 1.35,
              f"Source: {sources_str}  ─  {date.today().strftime('%Y/%m/%d')}",
              ha="center", fontsize=8, color="#555566")
            t(ax, 6, 0.7,
              "Arco Capital — 資産運用事業部",
              ha="center", fontsize=8, color="#333344", fontweight="bold")

            tmp = tempfile.NamedTemporaryFile(
                suffix=f"_{ticker}_chart2.png", delete=False)
            tmp.close()
            fig.savefig(tmp.name, dpi=150, facecolor=BRAND_DARK,
                        bbox_inches="tight")
            plt.close(fig)
            return tmp.name

        except Exception as e:
            print(f"      ⚠️ chart2(business_why) エラー: {e}")
            return None

    def _chart_business_strategy(
        self, ticker: str, market_data: dict
    ) -> Optional[str]:
        """
        ビジネス構造スライド: トレード戦略マトリクス（テーブル形式）
        """
        try:
            from matplotlib.font_manager import FontProperties
            fp = FontProperties(family=_JP_FONT) if _JP_FONT else None

            def t(ax, x, y, s, **kw):
                kw.setdefault("color", BRAND_WHITE)
                kw.setdefault("va", "center")
                if fp:
                    kw["fontproperties"] = fp
                ax.text(x, y, s, **kw)

            fig, ax = plt.subplots(figsize=(12, 7), facecolor=BRAND_DARK)
            ax.set_facecolor(BRAND_DARK)
            ax.set_xlim(0, 12)
            ax.set_ylim(0, 10)
            ax.axis("off")

            d = market_data

            # ── ヘッダー ───────────────────────────────────────────────
            t(ax, 6, 9.4, f"${ticker}  トレード戦略マトリクス",
              ha="center", fontsize=17, fontweight="bold", color=BRAND_GOLD)
            t(ax, 6, 8.85,
              f"現在値 ${d['close']:.2f}  ─  "
              f"SMA20 ${d['sma20']:.0f}  ─  "
              f"52週レンジ ${d['low_52w']:.0f} - ${d['high_52w']:.0f}",
              ha="center", fontsize=10, color="#AABBCC")
            ax.axhline(8.5, color=BRAND_GOLD, linewidth=0.8,
                       alpha=0.4, xmin=0.02, xmax=0.98)

            # ── テーブルヘッダー行 ─────────────────────────────────────
            cols_x = [0.4, 3.0, 6.0, 9.5]
            col_headers = ["アクション", "価格帯", "判断条件", "優先度"]
            col_widths   = [2.4, 2.8, 3.3, 2.2]

            header_y = 8.0
            header_bg = plt.Rectangle(
                (0.2, header_y - 0.35), 11.6, 0.7,
                facecolor="#1A2A3A", edgecolor=BRAND_GOLD, linewidth=1.0
            )
            ax.add_patch(header_bg)
            for cx, ch in zip(cols_x, col_headers):
                t(ax, cx, header_y, ch,
                  fontsize=10, fontweight="bold", color=BRAND_GOLD)

            # ── テーブルデータ行 ───────────────────────────────────────
            entry_lo = d["sma20"] * 0.99
            entry_hi = d["sma20"] * 1.03
            sl_price = d["sma50"] * 0.98 if not np.isnan(d.get("sma50", float("nan"))) \
                       else d["sma20"] * 0.94

            # (ラベル, 価格, 条件, 優先度, 背景色, 枠色, ドット色)
            rows = [
                ("エントリー検討",
                 f"${entry_lo:.0f} - ${entry_hi:.0f}",
                 "SMA20近辺での出来高増加反発",
                 "★★★",
                 "#FFD70018", BRAND_GOLD, BRAND_GOLD),
                ("損切りライン",
                 f"${sl_price:.0f} 割れ",
                 "SMA50下抜け＋出来高増加確認",
                 "★★★",
                 "#FF444418", BRAND_RED, BRAND_RED),
                ("利確ライン 1",
                 f"${d['high_52w']:.0f}",
                 "52週高値更新・勢い継続確認",
                 "★★",
                 "#00CC6618", BRAND_GREEN, BRAND_GREEN),
                ("利確ライン 2",
                 f"${d['bb_upper']:.0f} 付近",
                 "ボリバン上限・RSI過熱域到達",
                 "★",
                 "#00996618", "#00AA55", "#00AA55"),
            ]

            row_h = 1.3
            for ri, (action, price, cond, prio, bg_col, edge_col, dot_col) in enumerate(rows):
                ry = header_y - 0.65 - (ri + 1) * row_h
                row_bg = plt.Rectangle(
                    (0.2, ry - 0.45), 11.6, row_h - 0.05,
                    facecolor=bg_col, edgecolor=edge_col,
                    linewidth=0.8, linestyle="--"
                )
                ax.add_patch(row_bg)
                # 色ドット（絵文字の代わり）— 各行の左端に配置
                dot = plt.Circle((0.35, ry), 0.16,
                                 color=dot_col, zorder=4)
                ax.add_patch(dot)

                vals = [action, price, cond, prio]
                for cx, val in zip(cols_x, vals):
                    t(ax, cx, ry, val, fontsize=9.5, color=BRAND_WHITE)

            # ── フッター ───────────────────────────────────────────────
            footer_y = header_y - 0.65 - len(rows) * row_h - 0.3
            ax.axhline(footer_y, color="#2A3040", linewidth=0.5,
                       xmin=0.02, xmax=0.98)
            t(ax, 6, footer_y - 0.5,
              f"RSI {d['rsi']:.0f}  |  "
              f"MACD {'強気' if d['macd_hist'] > 0 else '弱気'}  |  "
              f"ボリバン下限 ${d['bb_lower']:.0f}  ─  "
              f"{date.today().strftime('%Y/%m/%d')}  Arco Capital",
              ha="center", fontsize=8, color="#555566")

            tmp = tempfile.NamedTemporaryFile(
                suffix=f"_{ticker}_chart5.png", delete=False)
            tmp.close()
            fig.savefig(tmp.name, dpi=150, facecolor=BRAND_DARK,
                        bbox_inches="tight")
            plt.close(fig)
            return tmp.name

        except Exception as e:
            print(f"      ⚠️ chart5(business_strategy) エラー: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4: 台本生成（実数値を渡す → Claude が factual な投稿を書く）
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_thread_scripts(
        self,
        ticker: str,
        market_data: dict,
        news_items: list[dict],
    ) -> list[dict]:
        """
        実データをClaudeに渡してスレッド台本を生成する。
        架空の数値は一切使用しない。
        """
        import anthropic

        today = date.today().strftime("%Y年%m月%d日")
        d = market_data

        # テクニカル判定
        rsi_comment = (
            "過買い圏（70超）" if d["rsi"] > 70
            else "過売り圏（30未満）" if d["rsi"] < 30
            else "中立圏"
        )
        macd_comment = (
            "強気転換（ゴールデンクロス）" if d["macd_crossed_bull"]
            else "弱気転換（デッドクロス）" if d["macd_crossed_bear"]
            else "強気継続" if d["macd_hist"] > 0
            else "弱気継続"
        )
        trend = "上昇" if d["close"] > d["sma20"] > d.get("sma50", 0) else \
                "下降" if d["close"] < d["sma20"] else "横ばい"

        news_text = "\n".join(
            f"- [{n['source']}] {n['headline']}" for n in news_items[:6]
        ) or "ニュースなし"

        system_prompt = """あなたはArco Capitalのシニアアナリスト兼Xコンテンツ戦略家です。
2026年版Xアルゴリズム（Grok AI統合、Rust基盤、6000特徴量の本ランキング）に完全最適化された個別銘柄デイリースレッドを制作します。

【2026年Xアルゴリズム最適化原則】
- Scoring Signal: リプライ(75.0) >> リポスト(20.0) >> プロフィールクリック(12.0) >> いいね(1.0)
- 滞在時間 30秒〜2分で1.5倍、2分超で11〜22倍の極大ブースト
  → 論理構造とデータ密度で熟読時間を設計する
- Grokのスパム判定を回避するため、無機質なAI文章ではなく「人間らしい主観や体験」を20%ブレンド
- 外部URLは本文に置かない（減点対象）

【絶対ルール（内容の深さ）】
- 一次情報（EDGAR 10-K/10-Q、公式決算、学術論文）を可能な限り具体的に引用
- 機関投資家レベルのクオンツ視点で語る（シャープレシオ、バックテスト、VIX、%B、MACDヒスト）
- 提供されていない数値を創作することは絶対禁止
- 使う数値は提供データから選んで引用（全部使う必要はない）
- 「なぜそうなっているか」の因果関係を常に明示する
- 断定的煽り禁止。リスクは誠実に開示

【絶対ルール（人間味20%ブレンド）】
以下の投稿には主観的フレーズを必ず1文だけ混ぜる:
- HOOK(投稿1): 「正直、この動きは予想外だった」「個人的には今日のビッグサプライズ」等
- ACTION(投稿5): 「自分が最も注視しているのは〇〇」「これは見逃したくないサイン」等
※WHY/HOW/TA(投稿2〜4)は客観分析に徹する

【絶対ルール（リプライ誘発＝スコア75.0獲得）】
最終投稿(index=5, ACTION)のbody末尾には必ず議論誘発の問いかけを1つ配置:
- 「皆さんはこの銘柄をどう見ていますか？」
- 「次のトリガーは決算か金利か、皆さんの見解は？」
※問いかけは💬絵文字をつけて独立セクションとする

【絶対ルール（可読性フォーマット）】
body構造:
1. 冒頭1〜2行で指を止めるフック
2. セクションごとに以下マーカーで見出し:
   - ▼ / ▶   単純項目・ポイント
   - ⚠️       注意・リスク
   - 🔻       下落・反転シグナル
   - 📊       データ・指標
   - 📚       一次情報引用（EDGAR/決算/論文）
   - 💬       議論誘発の問いかけ
3. 中黒(・) で項目列挙、または ①②③ で分岐整理
4. セクション間には必ず空行
5. body冒頭に "𝗜𝗡𝗦𝗜𝗚𝗛𝗧..." や罫線は書かない（コード側で自動付与）

【絶対ルール（出力スキーマ）】
JSON配列のみ。各要素のフィールド:
  - "index": 1〜5 の整数
  - "role":  "HOOK"/"WHY"/"HOW"/"TA"/"ACTION"
  - "title": 12〜22字の日本語見出し（【】なし、ハッシュタグなし）
  - "body":  上記フォーマット準拠の本文（目安200〜280字、滞在時間を稼ぐ密度）

【ハッシュタグ】
投稿1(index=1)のbody末尾にのみ、空行1つ空けて:
#米国株 #投資 #テクニカル分析 #株式投資 #資産運用"""

        user_prompt = f"""今日 {today} の実データをもとに、${ticker} のスレッドを作成してください。

【実市場データ】
銘柄: {ticker} ({d['company_name']})
セクター: {d['sector']}
終値: ${d['close']:.2f}
前日比: {d['change_pct']:+.2f}%
出来高: {d['volume']:,} (20日平均比 {d['volume_ratio']:.1f}x)
RSI(14): {d['rsi']:.1f} → {rsi_comment}
SMA20: ${d['sma20']:.2f}  SMA50: ${d.get('sma50', 0):.2f}
MACD: {d['macd']:.4f}  シグナル: {d['macd_signal']:.4f}  ヒスト: {d['macd_hist']:.4f}
MACDステータス: {macd_comment}
ボリンジャーバンド: 上限${d['bb_upper']:.2f} / 下限${d['bb_lower']:.2f}
52週高値: ${d['high_52w']:.2f}  52週安値: ${d['low_52w']:.2f}
直近20日レンジ: ${d['recent_low']:.2f} - ${d['recent_high']:.2f}
トレンド: {trend}（価格 vs SMA20 vs SMA50）

【本日のニュース（実データ）】
{news_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【5投稿の戦略的役割と心理的フック】

1. HOOK（衝撃型フック + 人間味1文） — title例: "〇〇の動きに異変、機関の資金が動いた"
   - 冒頭1〜2行で強烈なフック（数字の衝撃 or 意外性）
   - "▼ 背景" と "⚠️ 注意点" で因果整理
   - 人間味フレーズを1文混入（"正直、この動きは読めなかった" 等）
   - body末尾に空行1つ空けてハッシュタグ

2. WHY（一次情報型 / EDGAR・決算から検証） — title例: "EDGAR 10-Qが示す、上昇の真因"
   - "📚 一次情報" セクションで公式文書・決算資料の具体引用
   - "▼ 市場背景" でマクロ要因を補足
   - 二次情報の噂ではなく一次資料に基づく裏付け

3. HOW（機関投資家視点 / クオンツ分析型） — title例: "機関の買い残高から読み解く、資金フロー"
   - 📊 出来高比 / 📊 %B / 📊 オプションフロー の3データセクション
   - 学術的補足（"機械学習検証ではSMAとMACDが最高精度" 等の事実）
   - ⚠️ 薄商いや異常値を注意喚起

4. TA（学術根拠型テクニカル） — title例: "SMA×MACDで見る過熱度、機械学習の示唆"
   - 📊 RSI / 📊 MACD / 📊 BB の3データセクション
   - 各指標の意味を数値と学術的示唆で補足
   - 🔻 反転シグナルの可能性を明記

5. ACTION（教えてください型 + リプライ誘発） — title例: "今後の注目水準、皆さんはどう見ますか？"
   - ①②③ で観測すべき価格水準・指標値を提示
   - 🔻 反転シグナル一言
   - 人間味フレーズ1文（"自分が最も注視しているのは②" 等）
   - 💬 で議論誘発の問いかけを独立セクションとして末尾に配置

必ずJSON形式のみで回答してください。index は1〜5。"""

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = message.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        raw_posts = json.loads(raw)

        # ── コード側で統一フォーマットに整形 ─────────────────────────
        # Claude出力の title + body を結合して最終 text を生成。
        # x_theme_crew.py と同じヘルパーを使用して常に同じビジュアルを保証。
        posts: list[dict] = []
        total = min(len(raw_posts), 5)
        for i, p in enumerate(raw_posts[:5]):
            idx   = int(p.get("index", i + 1))
            role  = p.get("role", "")
            title = p.get("title", "").strip()
            body  = p.get("body", p.get("text", "")).strip()

            # 古いスキーマ互換
            if not title and body:
                first_line = body.split("\n", 1)[0]
                title = first_line.strip("【】 ").strip()
            title = title.split("#")[0].strip()

            # ─── 2026年Xアルゴリズム最適化: 最終投稿のリプライ誘発を確実化 ───
            # Claudeが問いかけを入れなかった場合のフォールバック。
            # 必ずリプライスコア75.0を狙える構造にする。
            if idx == total and idx >= 4:
                body = ensure_discussion_question(body)

            # 投稿1のハッシュタグ確認
            if idx == 1 and HASHTAGS not in body:
                body = body.rstrip() + f"\n\n{HASHTAGS}"

            text = format_post_text(idx, title, body)
            posts.append({
                "index": idx,
                "role": role,
                "title": title,
                "text": text,
            })

        return posts

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5: X投稿（tweepy v2 → v1 フォールバック）
    # ─────────────────────────────────────────────────────────────────────────

    def _post_thread(
        self,
        posts: list[dict],
        image_paths: list[Optional[str]],
    ) -> str:
        import tweepy

        auth = tweepy.OAuth1UserHandler(
            settings.x_api_key, settings.x_api_secret,
            settings.x_access_token, settings.x_access_token_secret,
        )
        api_v1 = tweepy.API(auth)
        client_v2 = tweepy.Client(
            consumer_key=settings.x_api_key,
            consumer_secret=settings.x_api_secret,
            access_token=settings.x_access_token,
            access_token_secret=settings.x_access_token_secret,
            wait_on_rate_limit=True,
        )

        first_id: Optional[str] = None
        reply_to_id: Optional[str] = None

        for i, post in enumerate(posts):
            text = post["text"]
            img_path = image_paths[i] if i < len(image_paths) else None

            media_ids = None
            if img_path and Path(img_path).exists():
                try:
                    media = api_v1.media_upload(filename=img_path)
                    media_ids = [media.media_id_string]
                    print(f"   📸 メディアアップロード完了: post {i+1}")
                except Exception as e:
                    print(f"   ⚠️ メディアアップロード失敗 (post {i+1}): {e}")

            # v2 create_tweet
            kwargs: dict = {"text": text}
            if media_ids:
                kwargs["media_ids"] = media_ids
            if reply_to_id:
                kwargs["in_reply_to_tweet_id"] = reply_to_id

            response = client_v2.create_tweet(**kwargs)
            tweet_id = response.data["id"]
            print(f"   ✅ 投稿完了: post {i+1} (id={tweet_id})")

            if first_id is None:
                first_id = tweet_id
            reply_to_id = tweet_id

            if i < len(posts) - 1:
                time.sleep(2)

        return (f"https://x.com/{settings.x_account_handle}/status/{first_id}"
                if first_id else "（ID取得失敗）")

    # ─────────────────────────────────────────────────────────────────────────
    # 保存・クリーンアップ
    # ─────────────────────────────────────────────────────────────────────────

    def _save_images(
        self, image_paths: list[Optional[str]], today: str
    ) -> list[Optional[str]]:
        save_dir = (settings.investment_division_dir
                    / "SNS投稿" / "queue" / date.today().isoformat())
        save_dir.mkdir(parents=True, exist_ok=True)
        saved = []
        for i, p in enumerate(image_paths):
            if p and Path(p).exists():
                dest = save_dir / f"post{i+1}.png"
                shutil.copy2(p, dest)
                saved.append(str(dest))
            else:
                saved.append(None)
        return saved

    def _save_result(
        self, today: str, ticker: str, posts: list[dict],
        thread_url: str, saved_images: list[Optional[str]]
    ) -> str:
        lines = [
            f"# X投資スレッド — {today} | ${ticker}",
            f"**モード**: {'ドライラン' if self.dry_run else '本番投稿'}",
            f"**スレッドURL**: {thread_url}",
            "",
        ]
        for i, post in enumerate(posts):
            idx = post.get("index", i + 1)
            role = post.get("role", "")
            text = post.get("text", "")
            img = saved_images[i] if i < len(saved_images) else None
            lines += [
                f"## 投稿{idx}: {role}",
                text,
                f"*画像*: `{img}`" if img else "",
                "",
            ]

        result = "\n".join(lines)
        save_dir = settings.investment_division_dir / "SNS投稿" / "queue"
        save_dir.mkdir(parents=True, exist_ok=True)
        path = save_dir / f"{date.today().isoformat()}_{ticker}_x_thread.md"
        path.write_text(result, encoding="utf-8")
        print(f"📄 保存: {path}")
        return result


# ─────────────────────────────────────────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────────────────────────────────────────

def _print_header(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def _preview_posts(posts: list[dict]) -> None:
    print("\n📝 生成されたスレッド原稿:\n" + "-" * 55)
    for post in posts:
        idx = post.get("index", "?")
        role = post.get("role", "")
        text = post.get("text", "")
        print(f"\n【投稿{idx}: {role}】({len(text)}文字)")
        print(text)
    print("\n" + "-" * 55 + "\n")


def _cleanup_images(paths: list[Optional[str]]) -> None:
    for p in paths:
        if p:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass
