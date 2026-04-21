"""
XArticleCrew — 長期マクロテーマ型Xアーティクル生成クルー

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
デイリーの銘柄スレッド（XThemeThreadCrew）とは別の部隊として、
半年〜数年の時間軸で動くマクロ・テーマに関する中量アーティクル（2000-3500字）を
執筆する。Goldman Sachs/Morgan Stanley級のリサーチノート相当。

【想定される用途例】
  - 「イラン戦争が株式相場にもたらしたもの」（地政学 × マーケット）
  - 「小休止を得たAI関連株の未来」（テクノロジーサイクル）
  - 「不安定な地政学と上がり続ける賃金、インフレ」（マクロ複合リスク）
  - 「ロボ・宇宙テーマの始動が呼ぶ鉱物資源銘柄の展望」（サプライチェーン）

【アーティクル構成（6-8セクション）】
  1. エグゼクティブサマリー — 論旨を3-5箇条書きで
  2. 歴史的文脈と背景 — 類似事象、なぜ今このテーマが重要か
  3. 現状分析とデータ — 主要指標の現在地
  4. セクター/銘柄インパクト — 受益者・被害者の具体的分析
  5. シナリオ分析 — 強気/中立/弱気 × 6-24ヶ月
  6. 投資インプリケーション — 具体銘柄・配分・タイミング
  7. リスク要因 — シナリオを崩す要素

【4-5枚のチャート】
  chart1: マクロイベントタイムライン + 主要アセット動向
  chart2: アセット相関マトリクス（ヒートマップ）
  chart3: 対象銘柄の長期パフォーマンス比較（6-24ヶ月）
  chart4: シナリオテーブル（強気/中立/弱気別のリターン予測）
  chart5: 推奨ポートフォリオ配分（ドーナツ）

【2026年Xアルゴリズム最適化要素】
  - 一次情報引用（EDGAR, FRED, IMF, BIS 等）
  - 学術的補足とクオンツ視点
  - 人間味20%ブレンド
  - リプライ誘発セクションを末尾に
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

使用例:
    crew = XArticleCrew(
        title="イラン戦争が株式相場にもたらしたもの",
        context=(
            "2025年の中東情勢激化がもたらした原油・防衛・安全資産への波及。"
            "S&P500、WTI、金、VIX、DXY、エネルギー株の変動を定量分析。"
        ),
        dry_run=True,
    )
    crew.run()
"""

import json
import os
import re
import shutil
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as _fm
import numpy as np

from config.settings import settings


# ═════════════════════════════════════════════════════════════════════════════
# 日本語フォント設定
# ═════════════════════════════════════════════════════════════════════════════
def _setup_jp_font() -> str:
    for path in [
        r"C:\Windows\Fonts\meiryo.ttc",
        r"C:\Windows\Fonts\YuGothM.ttc",
        r"C:\Windows\Fonts\msgothic.ttc",
    ]:
        try:
            if Path(path).exists():
                _fm.fontManager.addfont(path)
                prop = _fm.FontProperties(fname=path)
                fname = prop.get_name()
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


# ═════════════════════════════════════════════════════════════════════════════
# ブランドカラー（XThemeThreadCrew と統一）
# ═════════════════════════════════════════════════════════════════════════════
BRAND_DARK  = "#0A0F1E"
BRAND_CYAN  = "#00D4FF"
BRAND_GOLD  = "#FFD700"
BRAND_WHITE = "#FFFFFF"
BRAND_RED   = "#FF4444"
BRAND_GREEN = "#00CC66"

# スライド用（コンサル風白背景）
SLD_BG      = "#FFFFFF"
SLD_DARK    = "#1E2D40"
SLD_TEXT    = "#2C3E50"
SLD_SUB     = "#6B7A8D"
SLD_RULE    = "#CBD5E1"
SLD_ROW     = "#F4F7FA"
SLD_HDR     = "#1E3A5F"
SLD_HDR_FG  = "#FFFFFF"
SLD_GRN     = "#15803D"
SLD_RED     = "#DC2626"
SLD_ORG     = "#D97706"

# アーティクル用ハッシュタグ（デイリースレッドと区別）
ARTICLE_HASHTAGS = "#マクロ分析 #投資戦略 #米国株 #日本株 #テーマ投資"

# デフォルトのマクロ監視リスト（全アーティクルで必ず取得）
DEFAULT_MACRO_WATCHLIST = [
    "SPY",    # S&P 500
    "QQQ",    # Nasdaq 100
    "^VIX",   # ボラティリティ指数
    "GLD",    # 金
    "USO",    # WTI原油
    "UUP",    # ドル指数（DXYの代替）
    "TLT",    # 20年超米国債
    "XLE",    # エネルギーセクター
    "XLK",    # テクノロジーセクター
    "XLF",    # 金融セクター
]


# ═════════════════════════════════════════════════════════════════════════════
# アーティクル整形ヘルパー
# ═════════════════════════════════════════════════════════════════════════════
# 太字タイトル用（XThemeThreadCrewと同じ Unicode Mathematical Sans-Serif Bold）
BOLD_ARTICLE  = "𝗔𝗥𝗧𝗜𝗖𝗟𝗘"
ARTICLE_RULE  = "═══════════════════════════════════"


def format_article_header(title: str, publish_date: str) -> str:
    """アーティクルのヘッダ部分を統一フォーマットで生成"""
    return (
        f"{BOLD_ARTICLE}  |  {publish_date}\n"
        f"{ARTICLE_RULE}\n\n"
        f"【{title}】\n"
    )


def slugify(title: str) -> str:
    """日本語タイトルをファイル名用スラッグに変換（最初の30字+日付）"""
    # 非英数/日本語を除去
    clean = re.sub(r"[^\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]+", "_", title)
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean[:30]


# ═════════════════════════════════════════════════════════════════════════════
# メインクラス
# ═════════════════════════════════════════════════════════════════════════════
class XArticleCrew:
    """
    長期マクロテーマ型Xアーティクル生成クルー。

    Args:
        title:        アーティクルのタイトル（必須、自由記述）
        context:      テーマの要点・焦点（任意、Claudeへのヒント）
        tickers:      明示指定するアセット/銘柄（任意、省略時は自動抽出）
        target_length: "short"(2000-2500字) / "medium"(2500-3500字, 既定) / "long"(3500-5000字)
        time_horizon: 分析の時間軸 "6months" / "12months"(既定) / "24months"
        dry_run:      True = 生成のみ（Composerも開かない）

    【投稿経路の原則】
    このクルーは X Articles（記事機能）専用です。
    - 通常ポスト（create_tweet 経由のロングツイート）は投稿しません
    - `dry_run=False` の場合、MD を保存した上で Chrome の Article Composer 用の
      コピー&ペースト向け出力を作成します（file:// 貼り付けガイドを表示）
    - 最終的な Publish はユーザーがブラウザで手動実行します
    """

    def __init__(
        self,
        title: str,
        context: str = "",
        tickers: list[str] = None,
        target_length: str = "medium",
        time_horizon: str = "12months",
        dry_run: bool = True,
    ):
        if not title.strip():
            raise ValueError("title は必須です")
        self.title = title.strip()
        self.context = context.strip()
        self.explicit_tickers = [t.upper() if "." not in t else t for t in (tickers or [])]
        self.target_length = target_length
        self.time_horizon = time_horizon
        self.dry_run = dry_run

        # 長さ目標（文字数）
        self._length_range = {
            "short":  (2000, 2500),
            "medium": (2500, 3500),
            "long":   (3500, 5000),
        }.get(target_length, (2500, 3500))

        # 時間軸 → yfinance期間変換
        self._period_map = {
            "6months":  "6mo",
            "12months": "1y",
            "24months": "2y",
        }
        self.yf_period = self._period_map.get(time_horizon, "1y")

        self.tickers: list[str] = []   # run() で確定

    # ─────────────────────────────────────────────────────────────────────────
    def run(self) -> str:
        today = date.today().strftime("%Y年%m月%d日")
        mode_str = "🔍 ドライラン" if self.dry_run else "🚀 本番モード"
        _ph(f"XArticleCrew 起動 — {today}")
        print(f"  タイトル: {self.title}")
        if self.context:
            print(f"  要点: {self.context[:80]}{'...' if len(self.context) > 80 else ''}")
        print(f"  長さ目標: {self.target_length} ({self._length_range[0]}〜{self._length_range[1]}字)")
        print(f"  時間軸: {self.time_horizon}")
        print(f"  モード: {mode_str}\n")

        # STEP 1: 関連アセット抽出
        print("🔍 STEP 1/5: 関連アセット抽出中...\n")
        self.tickers = self._resolve_tickers()
        print(f"   → 対象{len(self.tickers)}アセット: {', '.join(self.tickers[:10])}\n")

        # STEP 2: マクロデータ収集
        print("📊 STEP 2/5: マクロデータ収集中...\n")
        market_data = self._fetch_market_data(self.tickers)
        news_items = self._fetch_news(self.title, self.context)
        print(f"   → {len(market_data)}アセットのデータ取得、{len(news_items)}件のニュース\n")

        # STEP 3: チャート生成
        print("📈 STEP 3/5: アーティクル用チャート生成中...\n")
        chart_paths = self._generate_charts(market_data, news_items)
        print(f"   → {sum(1 for p in chart_paths if p)}枚生成\n")

        # STEP 4: 本文生成
        print("✍️  STEP 4/5: アーティクル本文生成中 (Claude Opus)...\n")
        article_md = self._generate_article(market_data, news_items)
        char_count = len(re.sub(r"[\s\n]", "", article_md))
        print(f"   → 本文生成完了 ({char_count}字)\n")

        # STEP 5: 保存 + X Articles Composer 向けガイド出力
        # ─────────────────────────────────────────────────────────────
        # このクルーは「X Articles（記事機能）」専用で、通常ツイート投稿はしません。
        # dry_run=False でも自動投稿は行わず、ユーザーが Chrome の Article Composer で
        # Publish ボタンを押すまでが運用フローです。
        thread_url = "（X Articlesで手動投稿）" if not self.dry_run else "（ドライラン）"
        print("📋 STEP 5/5: MD保存 + X Articles Composer 向けガイド生成\n")

        saved_paths = self._save_output(today, article_md, chart_paths, thread_url)
        composer_guide = self._build_article_composer_guide(article_md, saved_paths)

        _cleanup(chart_paths)

        _ph("XArticleCrew 完了")
        print(f"  MDパス: {saved_paths['md']}")
        print(f"  図ファイル: {saved_paths['dir']}")
        if not self.dry_run:
            print("\n" + composer_guide)
        print()
        return article_md

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: 関連アセット自動抽出
    # ─────────────────────────────────────────────────────────────────────────
    def _resolve_tickers(self) -> list[str]:
        """
        明示指定 + デフォルトマクロリスト + Claudeが文脈から抽出した銘柄 を統合。
        """
        # ベースセット: デフォルトマクロ
        result = list(DEFAULT_MACRO_WATCHLIST)

        # ユーザー明示指定を追加
        for t in self.explicit_tickers:
            if t not in result:
                result.append(t)

        # Claude による文脈ベース抽出
        extracted = self._extract_tickers_from_context()
        for t in extracted:
            if t not in result:
                result.append(t)

        # 最大20銘柄に制限（データ取得コスト管理）
        return result[:20]

    def _extract_tickers_from_context(self) -> list[str]:
        """Claude Haikuでタイトル・文脈から関連ティッカーを抽出"""
        try:
            import anthropic
            prompt = f"""以下のアーティクルテーマから、関連する米国/日本/グローバル市場のティッカー（ETF含む）を最大10個抽出してください。

タイトル: {self.title}
要点: {self.context or "（指定なし）"}

出力ルール:
- JSON配列のみで返す（他のテキスト不要）
- 米国銘柄: NVDA, TSLA のような単純コード
- 日本銘柄: 7203.T, 6758.T のように .T サフィックス
- ETF: REMX(レアアース), ITA(防衛), URA(ウラン), XBI(バイオ) 等、テーマに合うものを優先
- 既に有名な銘柄・流動性の高いものを優先
- タイトルに直接関連するものを重視

例: ["MP", "LYSDY", "REMX", "ALB", "LIT", "FCX"]"""
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            msg = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            tickers = json.loads(raw)
            if isinstance(tickers, list):
                return [t.upper() if "." not in t else t for t in tickers[:10]]
        except Exception as e:
            print(f"   ⚠️ ティッカー自動抽出エラー: {e}")
        return []

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: データ収集
    # ─────────────────────────────────────────────────────────────────────────
    def _fetch_market_data(self, tickers: list[str]) -> dict:
        """yfinance で長期データ取得 + テクニカル指標計算"""
        import yfinance as yf
        result = {}
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                df = stock.history(period=self.yf_period, interval="1d")
                if df.empty or len(df) < 20:
                    continue

                close = float(df["Close"].iloc[-1])
                start = float(df["Close"].iloc[0])
                total_return = (close - start) / start * 100

                # ボラティリティ（年率）
                daily_returns = df["Close"].pct_change().dropna()
                volatility = float(daily_returns.std() * np.sqrt(252) * 100)

                # シャープレシオ（リスクフリー=4%と仮定）
                mean_annual_return = float(daily_returns.mean() * 252 * 100)
                sharpe = (mean_annual_return - 4.0) / volatility if volatility > 0 else 0.0

                # 最大ドローダウン
                cummax = df["Close"].cummax()
                drawdown = (df["Close"] - cummax) / cummax * 100
                max_dd = float(drawdown.min())

                # 会社名
                info = {}
                try:
                    info = stock.info
                except Exception:
                    pass
                name = info.get("longName", info.get("shortName", ticker))

                result[ticker] = {
                    "ticker": ticker,
                    "name": name,
                    "close": close,
                    "total_return": total_return,
                    "volatility": volatility,
                    "sharpe": sharpe,
                    "max_drawdown": max_dd,
                    "df": df,
                }
            except Exception as e:
                print(f"   ⚠️ {ticker} 取得エラー: {e}")
        return result

    def _fetch_news(self, title: str, context: str) -> list[dict]:
        """ニュース収集（Reuters, Yahoo Finance）"""
        import urllib.request
        import xml.etree.ElementTree as ET

        items: list[dict] = []
        seen: set[str] = set()
        keywords = (title + " " + context).lower()

        def add(headline, summary, source, url=""):
            h = headline.strip()
            if h and h not in seen and len(h) > 10:
                seen.add(h)
                items.append({"headline": h, "summary": summary[:200],
                              "source": source, "url": url})

        for rss_url in [
            "https://feeds.reuters.com/reuters/businessNews",
            "https://feeds.reuters.com/reuters/technologyNews",
            "https://feeds.reuters.com/reuters/worldNews",
        ]:
            try:
                req = urllib.request.Request(
                    rss_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    tree = ET.parse(resp)
                for item in tree.iter("item"):
                    t = item.findtext("title") or ""
                    d = item.findtext("description") or ""
                    link = item.findtext("link") or ""
                    add(t, d, "Reuters", link)
            except Exception:
                pass

        return items[:20]

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: チャート生成（アーティクル専用）
    # ─────────────────────────────────────────────────────────────────────────
    def _generate_charts(self, market_data: dict, news_items: list[dict]) -> list[Optional[str]]:
        paths: list[Optional[str]] = []

        print("   📊 chart1: 主要アセット長期推移（リバスド）...")
        paths.append(self._chart_normalized_performance(market_data))

        print("   📊 chart2: アセット相関マトリクス（ヒートマップ）...")
        paths.append(self._chart_correlation_matrix(market_data))

        print("   📊 chart3: リスク/リターン散布図（アセット比較）...")
        paths.append(self._chart_risk_return(market_data))

        print("   📊 chart4: シナリオ分析テーブル（強気/中立/弱気）...")
        paths.append(self._chart_scenario_table(market_data))

        return paths

    def _chart_normalized_performance(self, market_data: dict) -> Optional[str]:
        """主要アセットをリバスド（期初=100）で長期推移比較"""
        try:
            from matplotlib.font_manager import FontProperties
            fp = FontProperties(family=_JP_FONT) if _JP_FONT else None

            # 上位8アセット（SPY必須+ リターン絶対値上位）
            sorted_items = sorted(
                market_data.items(),
                key=lambda kv: abs(kv[1].get("total_return", 0)),
                reverse=True,
            )
            # SPY を強制的に先頭（比較基準）
            if "SPY" in market_data and "SPY" not in [k for k, _ in sorted_items[:8]]:
                sorted_items = [("SPY", market_data["SPY"])] + [
                    (k, v) for k, v in sorted_items if k != "SPY"
                ]
            top = sorted_items[:8]

            fig, ax = plt.subplots(figsize=(12, 7), facecolor=SLD_BG)
            ax.set_facecolor(SLD_BG)

            colors = [
                SLD_DARK, SLD_RED, SLD_GRN, SLD_ORG,
                BRAND_CYAN, "#7C3AED", "#EC4899", "#0891B2",
            ]

            for i, (ticker, d) in enumerate(top):
                df = d["df"]
                if df.empty:
                    continue
                normalized = df["Close"] / df["Close"].iloc[0] * 100
                label = f"{ticker} ({d['total_return']:+.1f}%)"
                ax.plot(df.index, normalized, color=colors[i % len(colors)],
                        linewidth=1.8, label=label, alpha=0.9)

            # 100基準線
            ax.axhline(100, color=SLD_SUB, linestyle="--", linewidth=0.8, alpha=0.5)

            ax.set_title(f"主要アセット パフォーマンス推移（期初=100, {self.time_horizon}）",
                         color=SLD_DARK, fontsize=14, fontweight="bold",
                         fontproperties=fp if fp else None, pad=14)
            ax.set_ylabel("リバスド値", color=SLD_SUB, fontsize=10,
                          fontproperties=fp if fp else None)
            ax.tick_params(colors=SLD_SUB, labelsize=9)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y/%m"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            for spine in ax.spines.values():
                spine.set_color(SLD_RULE)
            ax.grid(color=SLD_RULE, linestyle="--", alpha=0.5, axis="y")
            ax.legend(loc="upper left", fontsize=9, frameon=True,
                      facecolor=SLD_BG, edgecolor=SLD_RULE,
                      prop=fp if fp else None, ncol=2)

            plt.tight_layout()
            tmp = tempfile.NamedTemporaryFile(suffix="_article_chart1.png", delete=False)
            tmp.close()
            fig.savefig(tmp.name, dpi=150, facecolor=SLD_BG, bbox_inches="tight")
            plt.close(fig)
            return tmp.name
        except Exception as e:
            print(f"      ⚠️ chart1 エラー: {e}")
            return None

    def _chart_correlation_matrix(self, market_data: dict) -> Optional[str]:
        """アセット間相関マトリクス（ヒートマップ）"""
        try:
            from matplotlib.font_manager import FontProperties
            fp = FontProperties(family=_JP_FONT) if _JP_FONT else None

            # 日次リターン行列を構築
            sorted_items = sorted(
                market_data.items(),
                key=lambda kv: abs(kv[1].get("total_return", 0)),
                reverse=True,
            )
            top = sorted_items[:10]
            if len(top) < 3:
                return None

            # 日付を揃える（timezone差によるdropna問題を回避するため、date単位に正規化）
            import pandas as pd
            closes = {}
            for ticker, d in top:
                s = d["df"]["Close"].copy()
                # timezone-aware → date単位に正規化
                try:
                    s.index = s.index.tz_localize(None)
                except (AttributeError, TypeError):
                    pass
                s.index = pd.to_datetime(s.index).normalize()
                closes[ticker] = s
            df_prices = pd.DataFrame(closes).dropna()
            if df_prices.empty or len(df_prices) < 20:
                return None

            returns = df_prices.pct_change().dropna()
            corr = returns.corr().values
            labels = list(returns.columns)

            fig, ax = plt.subplots(figsize=(10, 8), facecolor=SLD_BG)
            im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")

            # 数値を各セルに表示
            for i in range(len(labels)):
                for j in range(len(labels)):
                    v = corr[i, j]
                    color = SLD_BG if abs(v) > 0.6 else SLD_DARK
                    ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                            color=color, fontsize=9, fontweight="bold")

            ax.set_xticks(range(len(labels)))
            ax.set_yticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha="right",
                               color=SLD_TEXT, fontsize=9,
                               fontproperties=fp if fp else None)
            ax.set_yticklabels(labels, color=SLD_TEXT, fontsize=9,
                               fontproperties=fp if fp else None)

            ax.set_title(f"アセット相関マトリクス（直近{self.time_horizon}・日次リターン）",
                         color=SLD_DARK, fontsize=13, fontweight="bold",
                         fontproperties=fp if fp else None, pad=14)

            cbar = fig.colorbar(im, ax=ax, shrink=0.8)
            cbar.ax.tick_params(colors=SLD_SUB, labelsize=9)
            cbar.outline.set_edgecolor(SLD_RULE)

            plt.tight_layout()
            tmp = tempfile.NamedTemporaryFile(suffix="_article_chart2.png", delete=False)
            tmp.close()
            fig.savefig(tmp.name, dpi=150, facecolor=SLD_BG, bbox_inches="tight")
            plt.close(fig)
            return tmp.name
        except Exception as e:
            print(f"      ⚠️ chart2 エラー: {e}")
            return None

    def _chart_risk_return(self, market_data: dict) -> Optional[str]:
        """リスク/リターン散布図"""
        try:
            from matplotlib.font_manager import FontProperties
            fp = FontProperties(family=_JP_FONT) if _JP_FONT else None

            tickers = list(market_data.keys())
            if len(tickers) < 3:
                return None

            xs = [market_data[t]["volatility"] for t in tickers]
            ys = [market_data[t]["total_return"] for t in tickers]

            fig, ax = plt.subplots(figsize=(11, 7), facecolor=SLD_BG)
            ax.set_facecolor(SLD_BG)

            # 各点の色はシャープレシオで決定
            sharpes = [market_data[t]["sharpe"] for t in tickers]
            sizes = [abs(market_data[t]["total_return"]) * 10 + 80 for t in tickers]

            scatter = ax.scatter(xs, ys, c=sharpes, s=sizes,
                                 cmap="RdYlGn", alpha=0.75,
                                 edgecolors=SLD_DARK, linewidths=1.0,
                                 vmin=-1, vmax=2)

            # ティッカーラベル
            for t, x, y in zip(tickers, xs, ys):
                ax.annotate(t, (x, y), fontsize=9, color=SLD_DARK,
                            fontweight="bold",
                            xytext=(7, 5), textcoords="offset points",
                            fontproperties=fp if fp else None)

            # ゼロ基準線
            ax.axhline(0, color=SLD_SUB, linestyle="--", linewidth=0.8, alpha=0.5)

            ax.set_xlabel("ボラティリティ（年率・%）", color=SLD_SUB, fontsize=10,
                          fontproperties=fp if fp else None)
            ax.set_ylabel("トータルリターン（%）", color=SLD_SUB, fontsize=10,
                          fontproperties=fp if fp else None)
            ax.set_title(f"リスク/リターン・マップ（{self.time_horizon}・色=シャープレシオ）",
                         color=SLD_DARK, fontsize=13, fontweight="bold",
                         fontproperties=fp if fp else None, pad=14)
            ax.tick_params(colors=SLD_SUB, labelsize=9)
            for spine in ax.spines.values():
                spine.set_color(SLD_RULE)
            ax.grid(color=SLD_RULE, linestyle="--", alpha=0.4)

            cbar = fig.colorbar(scatter, ax=ax, shrink=0.8)
            cbar.set_label("シャープレシオ", color=SLD_SUB, fontsize=9,
                           fontproperties=fp if fp else None)
            cbar.ax.tick_params(colors=SLD_SUB, labelsize=9)

            plt.tight_layout()
            tmp = tempfile.NamedTemporaryFile(suffix="_article_chart3.png", delete=False)
            tmp.close()
            fig.savefig(tmp.name, dpi=150, facecolor=SLD_BG, bbox_inches="tight")
            plt.close(fig)
            return tmp.name
        except Exception as e:
            print(f"      ⚠️ chart3 エラー: {e}")
            return None

    def _chart_scenario_table(self, market_data: dict) -> Optional[str]:
        """
        シナリオ分析テーブル: 強気/中立/弱気シナリオの想定リターンを
        Claude Haikuに推定させてテーブル表示する
        """
        try:
            from matplotlib.font_manager import FontProperties
            fp = FontProperties(family=_JP_FONT) if _JP_FONT else None

            scenarios = self._build_scenario_data(market_data)

            fig, ax = plt.subplots(figsize=(12, 7), facecolor=SLD_BG)
            ax.set_facecolor(SLD_BG)
            ax.set_xlim(0, 12)
            ax.set_ylim(0, 10)
            ax.axis("off")

            # タイトル
            ax.text(6, 9.5, f"{self.time_horizon} シナリオ分析  ─  想定リターン",
                    ha="center", fontsize=16, fontweight="bold",
                    color=SLD_DARK,
                    fontproperties=fp if fp else None)
            ax.axhline(9.1, color=BRAND_CYAN, linewidth=2.0, xmin=0.02, xmax=0.98)

            # テーブルヘッダ
            headers = ["アセット / セクター", "強気シナリオ", "中立シナリオ", "弱気シナリオ", "確度"]
            col_x = [0.5, 3.8, 6.3, 8.8, 11.0]
            hdr_y = 8.3

            ax.add_patch(plt.Rectangle((0.2, hdr_y - 0.35), 11.6, 0.7,
                                        facecolor=SLD_HDR, edgecolor="none", zorder=2))
            for cx, h in zip(col_x, headers):
                ax.text(cx, hdr_y, h, ha="left" if cx < 3 else "center", va="center",
                        fontsize=10, fontweight="bold", color=SLD_HDR_FG,
                        fontproperties=fp if fp else None, zorder=3)

            # データ行
            row_h = 0.9
            for ri, row in enumerate(scenarios[:6]):
                ry = hdr_y - 0.5 - (ri + 1) * row_h
                bg = SLD_ROW if ri % 2 == 0 else SLD_BG
                ax.add_patch(plt.Rectangle((0.2, ry - 0.35), 11.6, row_h - 0.05,
                                            facecolor=bg, edgecolor=SLD_RULE,
                                            linewidth=0.5, zorder=1))

                cells = [
                    row.get("asset", ""),
                    row.get("bull", ""),
                    row.get("base", ""),
                    row.get("bear", ""),
                    row.get("confidence", ""),
                ]
                cell_colors = [
                    SLD_DARK,
                    SLD_GRN,
                    SLD_TEXT,
                    SLD_RED,
                    SLD_ORG,
                ]
                for cx, val, c in zip(col_x, cells, cell_colors):
                    ha = "left" if cx < 3 else "center"
                    ax.text(cx, ry, val, ha=ha, va="center",
                            fontsize=9.5, color=c, fontweight="bold",
                            fontproperties=fp if fp else None, zorder=3)

            # フッタ
            ax.axhline(0.8, color=SLD_RULE, linewidth=0.5, xmin=0.02, xmax=0.98)
            ax.text(6, 0.5, f"分析日: {date.today().strftime('%Y/%m/%d')}  ─  Arco Capital Research",
                    ha="center", fontsize=9, color=SLD_SUB,
                    fontproperties=fp if fp else None)

            tmp = tempfile.NamedTemporaryFile(suffix="_article_chart4.png", delete=False)
            tmp.close()
            fig.savefig(tmp.name, dpi=150, facecolor=SLD_BG, bbox_inches="tight")
            plt.close(fig)
            return tmp.name
        except Exception as e:
            print(f"      ⚠️ chart4 エラー: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _build_scenario_data(self, market_data: dict) -> list[dict]:
        """Claude Haiku でシナリオリターン予測を生成"""
        try:
            import anthropic
            tickers_info = "\n".join(
                f"- {t}: リターン{d['total_return']:+.1f}%, "
                f"ボラ{d['volatility']:.1f}%, シャープ{d['sharpe']:.2f}"
                for t, d in list(market_data.items())[:10]
            )
            prompt = f"""以下のアーティクルテーマについて、主要アセット6つのシナリオ別リターンを予測してください。

タイトル: {self.title}
要点: {self.context}

直近{self.time_horizon}のアセットデータ:
{tickers_info}

以下のJSON配列のみで返してください。アセットは多様性を持たせ、
指数/セクターETF/個別銘柄をバランスよく含めてください。
ティッカーは日本語表記を添える（例: "NVDA (エヌビディア)"）:
[
  {{
    "asset": "SPY (S&P500)",
    "bull": "+18%",
    "base": "+8%",
    "bear": "-12%",
    "confidence": "中"
  }},
  ...6行
]

確度は 高/中/低 の3段階。シナリオリターンは現実的な値（極端すぎない）で。"""
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            msg = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=800,
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
            print(f"      ⚠️ シナリオ生成エラー: {e}")
            # フォールバック
            return [
                {"asset": "SPY (S&P500)",  "bull": "+15%", "base": "+8%",  "bear": "-10%", "confidence": "中"},
                {"asset": "QQQ (Nasdaq)",  "bull": "+20%", "base": "+10%", "bear": "-15%", "confidence": "中"},
                {"asset": "GLD (金)",      "bull": "+12%", "base": "+5%",  "bear": "-3%",  "confidence": "高"},
                {"asset": "TLT (長期債)",  "bull": "+10%", "base": "+4%",  "bear": "-8%",  "confidence": "低"},
                {"asset": "XLE (エネルギー)", "bull": "+25%", "base": "+6%", "bear": "-18%", "confidence": "低"},
                {"asset": "^VIX (ボラ)",    "bull": "-20%", "base": "+0%",  "bear": "+40%", "confidence": "低"},
            ]

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4: アーティクル本文生成
    # ─────────────────────────────────────────────────────────────────────────
    def _generate_article(self, market_data: dict, news_items: list[dict]) -> str:
        """Claude Opusで本文生成（Markdown形式）"""
        import anthropic

        # 市場データサマリー
        md_lines = []
        for t, d in list(market_data.items())[:15]:
            md_lines.append(
                f"- {t} ({d['name'][:30]}): "
                f"リターン{d['total_return']:+.1f}%, "
                f"ボラ{d['volatility']:.1f}%, "
                f"シャープ{d['sharpe']:.2f}, "
                f"最大DD{d['max_drawdown']:.1f}%"
            )
        data_summary = "\n".join(md_lines)

        news_text = "\n".join(
            f"- [{n['source']}] {n['headline']}"
            for n in news_items[:10]
        ) or "（ニュースなし）"

        lo, hi = self._length_range
        today = date.today().strftime("%Y年%m月%d日")

        system_prompt = f"""あなたはArco CapitalのマクロストラテジストでXのArticle（記事投稿）を執筆します。
読者は金融リテラシーの高い個人投資家。SNSで読まれる記事なので、論文調ではなく「視覚的にメリハリのある読みやすい記事」にします。

【絶対禁止事項（フォーマット）】
- 長い段落を書くな。1段落は最大3行まで（1行=全角40字目安）
- 段落と段落の間は必ず空行を入れる
- `###` サブ見出しは使わない（`##` のみ）
- 「- **名前**：説明」形式の階層箇条書きは禁止
- 「皆さんは〜」「〜してみませんか」等のSNS風呼びかけ禁止
- 「あなたが機関投資家なら〜」の呼びかけ禁止
- 「議論を深めたい」等の執筆宣言禁止
- 論文調の長文はNG。SNS読者は3行以上続くと読まない

【文章スタイル（SNS向け）】
- 1つのアイデア = 1つの短段落（2-3行で完結）
- 数字は段落の主役。「MP Materials +264%」のように独立した行で強調可
- 短い断定文を重ねる。長い修飾語や接続詞の連鎖は避ける
- データは箇条書きの方が伝わる場合がある（3-5項目の並列列挙OK）
- リズムを意識：短い文 → 短い文 → 少し長めの結論、のような緩急

【箇条書きの使い方】
OK例:
  過去24ヶ月のリターン:
  - MP Materials +264%
  - URA +104%
  - REMX +103%
  - S&P500 +42%
NG例:
  - **1. コア・サテライト戦略**：... (階層・太字ラベル付き)
  - **コア(70%)**：... (項目名が太字の説明)

【絶対ルール（内容）】
- 一次情報（EDGAR、FRED、IMF等）を文中で引用
- クオンツ指標（シャープレシオ、ボラティリティ、最大DD）を具体的数値で
- 提供されていない数値を創作することは絶対禁止
- 結論を書く前に、必ず本文中で根拠を提示
- 煽り禁止。リスクも同等に扱う

【チャート配置（超重要）】
本文に {{CHART1}}〜{{CHART4}} のプレースホルダを、それぞれ
「その内容を議論している直前または直後の段落の横」に配置する。
画像をただ貼るのではなく、読者が画像を見るタイミングで本文の流れと一致させる。

  CHART1 = 主要アセット長期推移（リバスド比較）
  CHART2 = アセット相関マトリクス
  CHART3 = リスク/リターン散布図
  CHART4 = シナリオ別想定リターンテーブル

各チャートは最大1回。使わなくてもよい。本文に関連がなければ割愛。

【出力形式】
- Markdown本文のみ（説明不要）
- 本文総文字数目標: {lo}〜{hi}字（空白除く）
- 見出しは `##` のみ、4-5個
- 数字・比率・ティッカーは短い行で独立させ、目で追いやすく

【Xの記事投稿で映える書き出し例】
  過去24ヶ月で最もリターンを出したのは、テック株ではない。

  MP Materials +264%
  REMX +103%
  URA +104%

  S&P500の+42%を大きく上回る。

  その中心にあるのが「レアアース」だ。

このように、短い段落・空行・数字の独立行・断定調で読者の目を止めること。"""

        user_prompt = f"""本日 {today}、以下のマクロテーマについてXのArticle（記事）を執筆してください。

【テーマ】
{self.title}

【要点・焦点】
{self.context or "（指定なし: タイトルから最適な切り口を選択）"}

【時間軸】
{self.time_horizon}

【市場データ（直近{self.time_horizon}、対象{len(market_data)}アセット）】
{data_summary}

【関連ニュース（直近）】
{news_text}

【記事構成（4-5セクション / `##` のみ）】
テーマに合った自由な日本語見出しで、以下の流れを作る:

1. 冒頭（リードセクション）
   - 見出しは「〇〇の逆転」「〇〇が示すもの」等の示唆的なもの
   - 最初の1-2行で数字の衝撃を提示（例: "過去24ヶ月で〇〇は+264%"）
   - 短い段落で「なぜ今このテーマか」を2-3行で提示
   - {{CHART1}} をここに配置

2. 構造的背景
   - 3つの潮流や要因を短い段落で並べる
   - 箇条書き（4-5項目）で整理してもよい

3. データが示す市場の反応
   - 主要銘柄/ETFのリターン・ボラ・シャープを短段落で
   - {{CHART2}} または {{CHART3}} を配置

4. ポートフォリオへの含意
   - 配分の考え方を端的に（長い箇条書き・階層リストは禁止）
   - {{CHART4}} を配置

5. シナリオを崩すリスク
   - 逆風シナリオを3つ程度、短い段落で並べる

【冒頭の書き方 — 特に重要】
最初の2-3行で読者の指を止める。
長い修飾語・説明的な書き出しはNG。
具体例:
  OK: "過去24ヶ月で最もリターンを出したのは、テック株ではなかった。\\n\\nMP Materials +264%。"
  NG: "近年、グローバル市場において〇〇が注目を集めており、特に..."

【末尾】
SNS的問いかけ禁止。
分析の結論か、リスクへの警戒で自然に締める。
「しかし、このテーマは高リスク・高リターン。ポジションサイズの管理が全てだ。」程度の短い結び。

必ずMarkdown本文のみで回答してください。"""

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=8000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        article = message.content[0].text.strip()

        # マークダウンブロック除去
        if article.startswith("```"):
            article = article.split("```", 2)[1]
            if article.startswith("markdown"):
                article = article[8:]
            article = article.strip()

        return article

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5: X Articles Composer 向けガイド生成
    # ─────────────────────────────────────────────────────────────────────────
    # 【重要】このクルーは X Articles（記事機能）専用です。
    # 通常のロングツイート投稿（create_tweet）は実装しません。理由:
    #   - ユーザーの明示要望: 「記事」は必ず X Articles で投稿する
    #   - X Articles API は公開されていないため、Composer UI 経由が唯一の手段
    #   - 通常ポストと Articles は表示・保存・編集の挙動がまったく異なる
    # ─────────────────────────────────────────────────────────────────────────
    def _build_article_composer_guide(
        self,
        article_md: str,
        saved_paths: dict,
    ) -> str:
        """
        X Article Composer に貼り付けるためのガイドを生成する。

        出力内容:
          - Composer の URL
          - 貼り付け用のクリーンテキスト（Markdown記号除去）
          - 画像配置の指示
        """
        # Composer に貼り付けやすいクリーンテキストを生成
        clean_text = self._make_paste_ready_text(article_md)
        paste_path = Path(saved_paths["dir"]) / "x_article_paste.txt"
        paste_path.write_text(clean_text, encoding="utf-8")

        dir_abs = Path(saved_paths["dir"]).resolve()

        guide = (
            "━" * 60 + "\n"
            "  📝 X Articles 記事投稿ガイド（通常ツイートではありません）\n"
            + "━" * 60 + "\n"
            "\n"
            "【原則】このクルーは X Articles（記事機能）専用です。\n"
            "通常のロングツイートとして投稿することはありません。\n"
            "\n"
            "【手順】\n"
            f"1. Chrome で以下を開く:\n"
            f"   https://x.com/compose/articles\n"
            f"\n"
            f"2. Write ボタン → 新規 Article 作成\n"
            f"\n"
            f"3. タイトル欄に貼り付け:\n"
            f"   {self.title}\n"
            f"\n"
            f"4. 本文欄にペースト用テキストを貼り付け:\n"
            f"   {paste_path}\n"
            f"\n"
            f"5. ヘッダー画像（5:2アスペクト）をアップロード:\n"
            f"   {dir_abs}\\header_thumbnail.png (推奨)\n"
            f"   ※ 未作成の場合は crews/trading/x_article_crew.py の\n"
            f"     _generate_header_thumbnail() が chart1 を流用生成する\n"
            f"\n"
            f"6. 本文中の [画像N XXX] プレースホルダーを削除し、\n"
            f"   同じ位置にチャート画像をドラッグ&ドロップ:\n"
            f"   {dir_abs}\\chart1.png  →  [画像1] の位置\n"
            f"   {dir_abs}\\chart2.png  →  [画像3] の位置\n"
            f"   {dir_abs}\\chart3.png  →  [画像2] の位置\n"
            f"   {dir_abs}\\chart4.png  →  [画像4] の位置\n"
            f"\n"
            f"7. 最終確認してユーザーが Publish ボタンを押す\n"
            f"\n"
            + "━" * 60
        )
        return guide

    def _make_paste_ready_text(self, article_md: str) -> str:
        """
        Markdown 本文を X Article Composer に貼り付けやすい形に整形する。
        - `##` 等の見出し記号は除去（Composer UI側でSubheadingを手動適用）
        - `**bold**` は中の文字だけ残す（Composerは Markdown非対応のため）
        - 箇条書きの `- ` は維持（Composerで自動変換される）
        """
        text = article_md

        # 見出し記号を除去（行頭の #, ##, ### を消す）
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

        # 太字 **xxx** → xxx
        text = re.sub(r"\*\*([^*\n]+?)\*\*", r"\1", text)

        # 斜体 *xxx* → xxx（但し箇条書き先頭の *は残す用に慎重に）
        text = re.sub(r"(?<!\*)\*([^*\s][^*\n]*?[^*\s])\*(?!\*)", r"\1", text)

        # チャート画像のマークダウン記法を [画像N XXX] ラベルに変換
        # 例: ![図1: 主要アセット長期推移...](./chart1.png) → [画像1 主要アセット長期推移...]
        def _img_replace(m):
            alt = m.group(1)
            # "図1: XXX" → "画像1 XXX"
            m2 = re.match(r"図(\d+)[:：]\s*(.+)", alt)
            if m2:
                return f"\n[画像{m2.group(1)} {m2.group(2)}]\n"
            return f"\n[画像 {alt}]\n"
        text = re.sub(r"!\[([^\]]+)\]\([^)]+\)", _img_replace, text)

        # キャプションの斜体行 (*図1：XXX*) を除去
        text = re.sub(r"^\*図\d+[:：].+?\*\s*$", "", text, flags=re.MULTILINE)

        # 連続する空行を2つに圧縮
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    # ─────────────────────────────────────────────────────────────────────────
    # 保存・クリーンアップ
    # ─────────────────────────────────────────────────────────────────────────
    def _save_output(
        self,
        today: str,
        article_md: str,
        chart_paths: list[Optional[str]],
        thread_url: str,
    ) -> dict:
        """MD + チャート画像を永続化（チャートは本文中の {CHART1}..{CHART4} を置換して挿入）"""
        # アーティクル専用ディレクトリ
        base_dir = settings.investment_division_dir / "Articles"
        base_dir.mkdir(parents=True, exist_ok=True)

        slug = slugify(self.title)
        date_str = date.today().isoformat()
        dir_name = f"{date_str}_{slug}"
        article_dir = base_dir / dir_name
        article_dir.mkdir(parents=True, exist_ok=True)

        # チャート画像コピー
        saved_charts = []
        for i, p in enumerate(chart_paths):
            if p and Path(p).exists():
                dest = article_dir / f"chart{i+1}.png"
                shutil.copy2(p, dest)
                saved_charts.append(str(dest))
            else:
                saved_charts.append(None)

        # 本文中の {CHART1}..{CHART4} プレースホルダを画像マークダウンに置換
        chart_labels = [
            "主要アセット長期推移（期初=100のリバスド比較）",
            "アセット相関マトリクス（日次リターン）",
            "リスク/リターン・マップ（シャープレシオで色分け）",
            "シナリオ別想定リターン",
        ]
        body_with_charts = article_md
        used_charts = set()
        for i in range(4):
            placeholder = "{CHART" + str(i + 1) + "}"
            if placeholder in body_with_charts and i < len(saved_charts) and saved_charts[i]:
                label = chart_labels[i]
                fname = Path(saved_charts[i]).name
                replacement = f"\n\n![図{i+1}: {label}](./{fname})\n*図{i+1}：{label}*\n\n"
                body_with_charts = body_with_charts.replace(placeholder, replacement)
                used_charts.add(i)

        # 未使用のチャートは本文末尾に補足として追加
        unused_charts_md = []
        for i, path in enumerate(saved_charts):
            if path and i not in used_charts:
                label = chart_labels[i] if i < len(chart_labels) else f"chart{i+1}"
                fname = Path(path).name
                unused_charts_md.append(f"![図{i+1}: {label}](./{fname})")
                unused_charts_md.append(f"*図{i+1}：{label}*")
                unused_charts_md.append("")

        # 残ったプレースホルダ（使えなかったもの）は削除
        body_with_charts = re.sub(r"\{CHART\d\}\n?", "", body_with_charts)

        # Markdown本文作成（メタデータはフロントマタ風にコンパクト化）
        lines = [
            f"# {self.title}",
            "",
            f"*{today}｜対象アセット: {len(self.tickers)}銘柄｜時間軸: {self.time_horizon}*",
            "",
        ]
        if thread_url and thread_url != "（ドライラン）":
            lines.append(f"*X投稿: {thread_url}*")
            lines.append("")

        lines.append(body_with_charts.strip())

        if unused_charts_md:
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.extend(unused_charts_md)

        md_path = article_dir / "article.md"
        md_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"📄 保存: {md_path}")

        return {
            "md": str(md_path),
            "charts": saved_charts,
            "dir": str(article_dir),
        }


# ─────────────────────────────────────────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────────────────────────────────────────
def _ph(title: str) -> None:
    print(f"\n{'='*60}\n  {title}\n{'='*60}\n")


def _cleanup(paths: list[Optional[str]]) -> None:
    for p in paths:
        if p:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass
