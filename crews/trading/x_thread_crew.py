"""
XInvestmentThreadCrew — X投資スレッド自動投稿クルー（リアルデータ版）

【絶対条件】チャート・決算・数字はすべて実データに基づく。架空の数値は一切禁止。

毎朝7:30 JSTに実行し、5投稿のリプライチェーンを作成する。

スレッド構造（実データ駆動）:
  投稿1 HOOK:     「【速報】$XX 本日+X.X%急騰📈 なぜ？」+ リアルローソク足チャート
  投稿2 背景:     今日の実際のニュース・材料（Alpacaニュースより）
  投稿3 深掘り:   出来高・セクター動向・機関投資家の動き（実データ）
  投稿4 TA分析:   RSI/MACD/サポート・レジスタンス（実チャート分析）
  投稿5 戦略:     エントリーポイント・損切・利確ライン + CTA

フロー:
  1. 当日トップムーバー自動選定 (yfinance)
  2. ニュース収集 (Alpaca NewsClient)
  3. 実データからチャート生成 (mplfinance)
  4. 実数値をClaudeに渡して台本生成
  5. X投稿 (tweepy / Chrome fallback)

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
        r"C:\Windows\Fonts\yumin.ttf",
    ]
    for path in font_paths:
        try:
            from pathlib import Path as _Path
            if _Path(path).exists():
                _fm.fontManager.addfont(path)
                prop = _fm.FontProperties(fname=path)
                fname = prop.get_name()
                matplotlib.rcParams["font.family"] = fname
                matplotlib.rcParams["axes.unicode_minus"] = False
                return fname
        except Exception:
            continue
    # フォールバック: 英語ラベルのみ使用
    matplotlib.rcParams["axes.unicode_minus"] = False
    return ""

_JP_FONT = _setup_jp_font()

from config.settings import settings

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
        chart_paths = self._generate_charts(ticker, market_data)
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
        df = stock.history(period="3mo", interval="1d")
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

    def _generate_charts(self, ticker: str, market_data: dict) -> list[Optional[str]]:
        """
        実データからチャートを5枚生成する。
        投稿1,3,4は実チャート。投稿2,5はNano Banana。
        """
        df = market_data["df"]
        paths: list[Optional[str]] = []

        # 投稿1: ローソク足 + 出来高 + ボリンジャーバンド（60日）
        print("   📊 chart1: ローソク足+BB+出来高...")
        paths.append(self._chart_candle_bb(ticker, df, market_data))

        # 投稿2: Nano Banana（ニュース背景イメージ）
        print("   🎨 chart2: Nano Banana（ニュース背景）...")
        paths.append(self._generate_nano_banana_image(
            2, ticker,
            f"Breaking financial news about {ticker} stock, "
            "newspaper headlines, stock trading floor, urgent atmosphere, "
            "dark navy background, cyan accents"
        ))

        # 投稿3: ローソク足 + 出来高比較（20日平均線付き）
        print("   📊 chart3: 出来高比較チャート...")
        paths.append(self._chart_volume_analysis(ticker, df, market_data))

        # 投稿4: RSI + MACD テクニカルチャート
        print("   📊 chart4: RSI+MACDテクニカル...")
        paths.append(self._chart_technical(ticker, df, market_data))

        # 投稿5: Nano Banana（投資戦略イメージ）
        print("   🎨 chart5: Nano Banana（投資戦略）...")
        paths.append(self._generate_nano_banana_image(
            5, ticker,
            f"Investment strategy and stock trading, "
            "financial chart with entry and exit points, "
            "stop loss and take profit lines, professional trader mindset, "
            "dark navy background, gold accents, minimal text"
        ))

        return paths

    def _chart_candle_bb(self, ticker: str, df, market_data: dict) -> Optional[str]:
        """ローソク足 + ボリンジャーバンド + 出来高チャート"""
        try:
            import mplfinance as mpf

            df60 = df.tail(60).copy()

            # ボリンジャーバンド
            bb_mid = df["Close"].rolling(20).mean().tail(60)
            bb_std = df["Close"].rolling(20).std().tail(60)
            bb_upper = bb_mid + 2 * bb_std
            bb_lower = bb_mid - 2 * bb_std
            sma20 = df["Close"].rolling(20).mean().tail(60)
            sma50 = df["Close"].rolling(50).mean().tail(60)

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

            change_str = f"{market_data['change_pct']:+.2f}%"
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
                title=f"  ${ticker}  {market_data['close']:.2f} ({change_str})  ─ 60日チャート",
                ylabel="Price (USD)",
                ylabel_lower="Volume",
                figsize=(12, 7),
                returnfig=True,
                tight_layout=True,
            )
            # タイトル色
            fig.axes[0].title.set_color(BRAND_WHITE)
            fig.savefig(tmp.name, dpi=150, facecolor=BRAND_DARK, bbox_inches="tight")
            plt.close(fig)
            return tmp.name

        except Exception as e:
            print(f"      ⚠️ chart1 生成エラー: {e}")
            return None

    def _chart_volume_analysis(self, ticker: str, df, market_data: dict) -> Optional[str]:
        """出来高分析チャート（20日平均との比較）"""
        try:
            df20 = df.tail(20).copy()
            avg_vol = df["Volume"].rolling(20).mean().tail(20)

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7),
                                            gridspec_kw={"height_ratios": [3, 1]},
                                            facecolor=BRAND_DARK)
            fig.subplots_adjust(hspace=0.05)

            dates = df20.index
            x = np.arange(len(dates))

            # ローソク足
            for i, (idx, row) in enumerate(df20.iterrows()):
                color = BRAND_GREEN if row["Close"] >= row["Open"] else BRAND_RED
                ax1.plot([i, i], [row["Low"], row["High"]], color=color, linewidth=1)
                ax1.bar(i, abs(row["Close"] - row["Open"]),
                        bottom=min(row["Open"], row["Close"]),
                        color=color, width=0.7, alpha=0.85)

            # SMA20
            sma20 = df["Close"].rolling(20).mean().tail(20)
            ax1.plot(x, sma20.values, color=BRAND_GOLD, linewidth=1.2,
                     linestyle="--", label="SMA20")
            ax1.set_facecolor(BRAND_DARK)
            ax1.set_title(f"${ticker} — 出来高分析 (20日)", color=BRAND_WHITE, fontsize=13)
            ax1.set_ylabel("Price (USD)", color=BRAND_WHITE)
            ax1.tick_params(colors=BRAND_WHITE, labelbottom=False)
            ax1.legend(facecolor="#1A2030", labelcolor=BRAND_WHITE, fontsize=9)
            ax1.spines[:].set_color("#333344")
            ax1.grid(color="#1A2030", linestyle="--", alpha=0.5)

            # 出来高バー
            vol_colors = [BRAND_GREEN if df20["Close"].iloc[i] >= df20["Open"].iloc[i]
                          else BRAND_RED for i in range(len(df20))]
            ax2.bar(x, df20["Volume"].values, color=vol_colors, alpha=0.8, width=0.7)
            ax2.plot(x, avg_vol.values, color=BRAND_GOLD, linewidth=1.2,
                     linestyle="--", label=f"20日平均: {market_data['avg_volume_20']:,.0f}")
            ax2.set_facecolor(BRAND_DARK)
            ax2.set_ylabel("Volume", color=BRAND_WHITE, fontsize=9)
            ax2.tick_params(colors=BRAND_WHITE)
            ax2.legend(facecolor="#1A2030", labelcolor=BRAND_WHITE, fontsize=8)
            ax2.spines[:].set_color("#333344")
            ax2.grid(color="#1A2030", linestyle="--", alpha=0.5)

            # テキスト注釈
            vol_ratio = market_data["volume_ratio"]
            ax2.text(0.98, 0.85,
                     f"本日出来高: {market_data['volume']:,.0f}\n"
                     f"平均比: {vol_ratio:.1f}x",
                     transform=ax2.transAxes, ha="right", va="top",
                     color=BRAND_CYAN, fontsize=9,
                     bbox=dict(facecolor="#1A2030", alpha=0.8, edgecolor=BRAND_CYAN))

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
            ax1.set_title(
                f"${ticker} テクニカル分析  "
                f"RSI={market_data['rsi']:.1f}  "
                f"MACD={'🟢強気' if market_data['macd_hist'] > 0 else '🔴弱気'}",
                color=BRAND_WHITE, fontsize=12
            )
            ax1.set_ylabel("Price (USD)", color=BRAND_WHITE)
            ax1.tick_params(colors=BRAND_WHITE, labelbottom=False)
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
            ax2.set_ylabel("RSI(14)", color=BRAND_WHITE, fontsize=9)
            ax2.tick_params(colors=BRAND_WHITE, labelbottom=False)
            ax2.text(0.99, 0.85, f"RSI: {market_data['rsi']:.1f}",
                     transform=ax2.transAxes, ha="right",
                     color=BRAND_CYAN, fontsize=10)
            ax2.spines[:].set_color("#333344")
            ax2.grid(color="#1A2030", linestyle="--", alpha=0.4)

            # MACD
            hist_colors = [BRAND_GREEN if v > 0 else BRAND_RED for v in hist.values]
            ax3.bar(x, hist.values, color=hist_colors, alpha=0.7, width=0.7)
            ax3.plot(x, macd.values,  color=BRAND_CYAN,  linewidth=1.0, label="MACD")
            ax3.plot(x, sig.values,   color=BRAND_GOLD,  linewidth=1.0, label="Signal")
            ax3.axhline(0, color="#555566", linewidth=0.5)
            ax3.set_facecolor(BRAND_DARK)
            ax3.set_ylabel("MACD(12,26,9)", color=BRAND_WHITE, fontsize=9)
            ax3.tick_params(colors=BRAND_WHITE)
            ax3.legend(facecolor="#1A2030", labelcolor=BRAND_WHITE, fontsize=8,
                       loc="upper left")
            ax3.spines[:].set_color("#333344")
            ax3.grid(color="#1A2030", linestyle="--", alpha=0.4)

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
                f"Context: {ticker} stock investment content. "
                f"Style: premium financial infographic. "
                f"Background: dark navy ({BRAND_DARK}). "
                f"Accent colors: cyan ({BRAND_CYAN}), gold ({BRAND_GOLD}). "
                "Clean, modern, professional. No text overlay. 16:9 aspect ratio."
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

        system_prompt = """あなたはArco Capitalの投資アナリストです。
提供された「実データ」のみを使用してXスレッドを作成してください。

【絶対ルール】
- 提供されていない数値を作り上げることは絶対禁止
- すべての数値・パーセント・価格は提供データから引用すること
- 不確かな情報は「〜の可能性」と表現すること

【出力形式】JSON配列のみ（マークダウンブロック不要）
[
  {"index":1,"role":"HOOK","text":"...","image_description":"..."},
  ...
]

- 投稿1のみ末尾にハッシュタグ: #米国株 #投資 #テクニカル分析 #株式投資 #資産運用
- 各投稿200文字以内（日本語）
- 絵文字を1〜3個使用
- 読者が次を読みたくなる引きを作る"""

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

【5投稿の役割】
1. HOOK: 今日の動きを一言で表す衝撃的な数字（実数値を使う）
2. 背景(WHY): なぜ今日動いたか（ニュースの具体的な内容）
3. 深掘り(HOW): 出来高・テクニカルから機関動向を分析
4. TA分析(CHART): RSI/MACDを使った今後のシナリオ（強気/弱気）
5. 戦略(ACTION): 具体的なエントリー・損切・利確ライン + CTA

必ずJSON形式のみで回答してください。"""

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = message.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        posts = json.loads(raw)

        # 投稿1のハッシュタグを確認
        if posts and HASHTAGS not in posts[0]["text"]:
            posts[0]["text"] = posts[0]["text"].rstrip() + f"\n\n{HASHTAGS}"

        return posts[:5]

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
