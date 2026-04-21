"""
XEarningsThreadCrew — 米国決算ふりかえりスレッド型クルー

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
直近に決算発表された大型株トップ3を時価総額順で自動選定し、
「実績 vs 予想・ガイダンス・株価反応・アナリスト反応」をスレッドで配信する。

【スレッド構成（5投稿）】
  投稿1 HOOK:    今週決算3社のサマリー + 数字の衝撃
  投稿2 1社目:   実績/予想/ガイダンス/株価反応/示唆
  投稿3 2社目:   同上
  投稿4 3社目:   同上
  投稿5 総括:    全体の含意 + リプライ誘発の問いかけ

【4チャート】
  chart1: EPSサプライズ表 — 3社の予想 vs 実績 + 売上サプライズ
  chart2: 決算後株価反応棒グラフ — 1日/1週間/1ヶ月リターン
  chart3: フォワードPE比較 — 3社のバリュエーション + セクター中央値
  chart4: 出来高変化チャート — 決算前後の出来高推移（直近20日）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

使用例:
    crew = XEarningsThreadCrew(dry_run=True)
    crew.run()

    # 明示指定
    crew = XEarningsThreadCrew(tickers=["JPM","NFLX","JNJ"], dry_run=True)
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


def _setup_jp_font() -> str:
    for path in [r"C:\Windows\Fonts\meiryo.ttc", r"C:\Windows\Fonts\YuGothM.ttc"]:
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

from config.settings import settings
from crews.trading.x_theme_crew import (
    BOLD_INSIGHT, BOLD_DIGITS, THREAD_DIVIDER,
    format_post_text, ensure_discussion_question,
)

# ブランドカラー
BRAND_DARK  = "#0A0F1E"
BRAND_CYAN  = "#00D4FF"
BRAND_GOLD  = "#FFD700"
BRAND_WHITE = "#FFFFFF"
BRAND_RED   = "#FF4444"
BRAND_GREEN = "#00CC66"

# スライド用（コンサル白背景）
SLD_BG     = "#FFFFFF"
SLD_DARK   = "#1E2D40"
SLD_TEXT   = "#2C3E50"
SLD_SUB    = "#6B7A8D"
SLD_RULE   = "#CBD5E1"
SLD_ROW    = "#F4F7FA"
SLD_HDR    = "#1E3A5F"
SLD_HDR_FG = "#FFFFFF"
SLD_GRN    = "#15803D"
SLD_RED    = "#DC2626"
SLD_ORG    = "#D97706"

EARNINGS_HASHTAGS = "#決算 #米国株 #投資 #決算速報 #株式投資"

# 米国大型株プール（時価総額・流動性・話題性で選定）
# 決算シーズンに必ず注目される銘柄群
LARGECAP_POOL = [
    # メガキャップテック
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
    # 半導体
    "AVGO", "AMD", "TSM", "QCOM", "INTC",
    # 金融大手
    "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW",
    # ヘルスケア
    "LLY", "JNJ", "UNH", "PFE", "ABBV", "MRK",
    # 消費関連
    "WMT", "COST", "HD", "MCD", "KO", "PEP", "PG",
    # エネルギー
    "XOM", "CVX",
    # 通信・メディア
    "NFLX", "DIS", "T", "VZ",
    # その他大型
    "BRK-B", "V", "MA", "ORCL", "CRM",
]


class XEarningsThreadCrew:
    """
    米国決算ふりかえりスレッド型クルー。

    Args:
        tickers:    明示指定銘柄（カンマ区切り or リスト）。省略時は自動選定。
        days_back:  「直近n日に決算済み」の n（既定: 7）
        count:      取り上げる銘柄数（既定: 3）
        dry_run:    True = 投稿せず確認のみ
    """

    def __init__(
        self,
        tickers: list[str] = None,
        days_back: int = 7,
        count: int = 3,
        dry_run: bool = True,
    ):
        self.explicit_tickers = [t.upper() for t in tickers] if tickers else None
        self.days_back = days_back
        self.count = count
        self.dry_run = dry_run
        self.tickers: list[str] = []          # run() で確定
        self.earnings_data: dict = {}         # ticker → 詳細データ

    # ─────────────────────────────────────────────────────────────────────────
    def run(self) -> str:
        today = date.today().strftime("%Y年%m月%d日")
        mode = "🔍 ドライラン" if self.dry_run else "🚀 本番投稿"
        _ph(f"XEarningsThreadCrew 起動 — {today}")
        print(f"  モード: {mode}")
        print(f"  対象期間: 直近{self.days_back}日に発表された決算")
        print(f"  取り上げ件数: {self.count}社\n")

        # STEP 1: 直近決算済み銘柄の自動選定
        print(f"📅 STEP 1/5: 決算銘柄選定中...\n")
        self.tickers = self._select_recent_earnings_tickers()
        if not self.tickers:
            raise RuntimeError(f"直近{self.days_back}日に決算発表のあった大型株が見つかりませんでした")
        for t in self.tickers:
            print(f"   ✓ {t}")
        print()

        # STEP 2: 各社のデータ詳細取得
        print(f"📊 STEP 2/5: 各社の決算データ取得中...\n")
        for t in self.tickers:
            print(f"   📥 {t} ...")
            self.earnings_data[t] = self._fetch_company_earnings(t)
        print()

        # STEP 3: チャート生成
        print(f"📈 STEP 3/5: チャート生成中...\n")
        chart_paths = self._generate_charts()
        print(f"   → {sum(1 for p in chart_paths if p)}枚生成\n")

        # STEP 4: スレッド原稿生成
        print(f"✍️  STEP 4/5: スレッド原稿生成中（Claude Opus）...\n")
        posts = self._generate_thread_scripts()
        _preview(posts)

        # STEP 5: 投稿
        if self.dry_run:
            print("📋 STEP 5/5: ドライランのため投稿スキップ\n")
            thread_url = "（ドライラン）"
        else:
            print("🐦 STEP 5/5: X にスレッド投稿中...\n")
            try:
                thread_url = self._post_thread(posts, chart_paths)
            except Exception as e:
                thread_url = f"（投稿失敗: {e}）"
                print(f"⚠️ 投稿失敗: {e}\n")

        saved_charts = self._save_charts(chart_paths)
        result_md = self._save_result(today, posts, thread_url, saved_charts)
        _cleanup(chart_paths)

        _ph("XEarningsThreadCrew 完了")
        print(f"  スレッドURL: {thread_url}\n")
        return result_md

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: 銘柄選定
    # ─────────────────────────────────────────────────────────────────────────
    def _select_recent_earnings_tickers(self) -> list[str]:
        """
        大型株プールから「直近days_back日に決算発表があった」銘柄を抽出し、
        時価総額順に上位countを返す。
        """
        if self.explicit_tickers:
            print(f"   → 明示指定 {len(self.explicit_tickers)}銘柄を使用")
            return self.explicit_tickers[:self.count]

        import yfinance as yf
        today = date.today()
        threshold = today - timedelta(days=self.days_back)

        candidates = []  # (ticker, eps_est, eps_act, surp%, mcap, earnings_date)
        for t in LARGECAP_POOL:
            try:
                stock = yf.Ticker(t)
                ed = stock.earnings_dates
                if ed is None or len(ed) == 0:
                    continue
                # 直近の発表済み earnings を探す
                for idx, row in ed.iterrows():
                    try:
                        d = idx.date() if hasattr(idx, "date") else idx
                    except Exception:
                        continue
                    if not (threshold <= d <= today):
                        continue
                    eps_est = row.get("EPS Estimate", None)
                    eps_act = row.get("Reported EPS", None)
                    if eps_act is None or (isinstance(eps_act, float) and np.isnan(eps_act)):
                        continue  # まだ未発表
                    info = stock.info or {}
                    mcap = info.get("marketCap", 0) or 0
                    candidates.append({
                        "ticker": t, "earnings_date": d,
                        "eps_est": float(eps_est) if eps_est is not None else None,
                        "eps_act": float(eps_act),
                        "surprise_pct": float(row.get("Surprise(%)", 0)) if row.get("Surprise(%)") is not None else None,
                        "mcap": int(mcap),
                    })
                    break
            except Exception as e:
                print(f"   ⚠️ {t}: {e}")
                continue

        # 時価総額順
        candidates.sort(key=lambda c: c["mcap"], reverse=True)
        selected = [c["ticker"] for c in candidates[:self.count]]
        # キャッシュとして保存（後でfetch時に活用）
        self._candidates_cache = {c["ticker"]: c for c in candidates}
        return selected

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: 各社決算データ取得
    # ─────────────────────────────────────────────────────────────────────────
    def _fetch_company_earnings(self, ticker: str) -> dict:
        """
        各社の決算情報を網羅的に取得。
        - EPS 予想/実績/サプライズ%
        - 売上 予想/実績（あれば）
        - フォワードPE、トレーリングPE
        - 決算日からの 1D/1W/1M 株価リターン
        - 決算前後の出来高推移
        - アナリストレコメンデーション
        - 会社名、セクター
        """
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        d: dict = {
            "ticker": ticker,
            "name": info.get("longName", info.get("shortName", ticker)),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "market_cap": info.get("marketCap", 0),
            "forward_pe": info.get("forwardPE", None),
            "trailing_pe": info.get("trailingPE", None),
            "current_price": info.get("currentPrice", info.get("regularMarketPrice", None)),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh", None),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow", None),
            "recommendation": info.get("recommendationKey", ""),
            "target_mean": info.get("targetMeanPrice", None),
        }

        # キャッシュからEPS情報を取得
        cached = getattr(self, "_candidates_cache", {}).get(ticker)
        if cached:
            d.update({
                "earnings_date": cached["earnings_date"],
                "eps_est": cached["eps_est"],
                "eps_act": cached["eps_act"],
                "eps_surprise_pct": cached["surprise_pct"],
            })
        else:
            # 個別取得
            try:
                ed = stock.earnings_dates
                if ed is not None and len(ed) > 0:
                    for idx, row in ed.iterrows():
                        try:
                            dd = idx.date() if hasattr(idx, "date") else idx
                        except Exception: continue
                        if dd <= date.today():
                            ea = row.get("Reported EPS", None)
                            if ea is not None and not (isinstance(ea, float) and np.isnan(ea)):
                                d["earnings_date"] = dd
                                d["eps_est"] = float(row.get("EPS Estimate", 0)) if row.get("EPS Estimate") is not None else None
                                d["eps_act"] = float(ea)
                                d["eps_surprise_pct"] = float(row.get("Surprise(%)", 0)) if row.get("Surprise(%)") is not None else None
                                break
            except Exception:
                pass

        # 株価データ（決算日前後の動きを見る用）
        try:
            hist = stock.history(period="3mo", interval="1d")
            d["df_3m"] = hist
            if "earnings_date" in d:
                ed_date = d["earnings_date"]
                # 決算日付近の終値を抽出
                hist_idx = hist.index
                try: hist_idx_naive = hist_idx.tz_localize(None)
                except Exception: hist_idx_naive = hist_idx
                hist2 = hist.copy()
                hist2.index = hist_idx_naive

                ed_ts = np.datetime64(ed_date)
                # 決算日の終値 (or 前日)
                pre_idx = [i for i, t_ in enumerate(hist2.index) if t_.to_numpy() <= ed_ts]
                if pre_idx:
                    earnings_close = float(hist2["Close"].iloc[pre_idx[-1]])
                    d["earnings_close"] = earnings_close
                    earnings_pos = pre_idx[-1]
                    # 1日後・5日後・21日後（営業日ベース）の価格
                    for label, offset in [("ret_1d", 1), ("ret_1w", 5), ("ret_1m", 21)]:
                        target_pos = earnings_pos + offset
                        if target_pos < len(hist2):
                            future_close = float(hist2["Close"].iloc[target_pos])
                            d[label] = (future_close - earnings_close) / earnings_close * 100
                        else:
                            d[label] = None
                    # 出来高（決算前10日 vs 決算後10日）
                    pre_vol = hist2["Volume"].iloc[max(0, earnings_pos-10):earnings_pos].mean()
                    post_vol = hist2["Volume"].iloc[earnings_pos:earnings_pos+10].mean() if earnings_pos+10 <= len(hist2) else hist2["Volume"].iloc[earnings_pos:].mean()
                    d["volume_pre_avg"] = float(pre_vol) if pre_vol == pre_vol else None
                    d["volume_post_avg"] = float(post_vol) if post_vol == post_vol else None
                    d["volume_ratio"] = (d["volume_post_avg"] / d["volume_pre_avg"]) if d.get("volume_pre_avg") else None
                    d["earnings_pos"] = earnings_pos
        except Exception as e:
            print(f"      ⚠️ 株価取得エラー: {e}")

        # 売上データ（quarterly_income_stmt から最新を取得）
        try:
            qis = stock.quarterly_income_stmt
            if qis is not None and not qis.empty and "Total Revenue" in qis.index:
                d["revenue_actual"] = float(qis.loc["Total Revenue"].iloc[0])
                # 前年同期比 (4四半期前)
                if len(qis.columns) >= 5:
                    d["revenue_yoy"] = (d["revenue_actual"] - float(qis.loc["Total Revenue"].iloc[4])) / float(qis.loc["Total Revenue"].iloc[4]) * 100
        except Exception:
            pass

        return d

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: チャート生成（4枚）
    # ─────────────────────────────────────────────────────────────────────────
    def _generate_charts(self) -> list[Optional[str]]:
        paths: list[Optional[str]] = []
        print("   📊 chart1: EPSサプライズ表...")
        paths.append(self._chart_eps_surprise_table())
        print("   📊 chart2: 決算後株価反応棒グラフ...")
        paths.append(self._chart_post_earnings_returns())
        print("   📊 chart3: フォワードPE比較...")
        paths.append(self._chart_forward_pe_comparison())
        print("   📊 chart4: 決算前後の出来高変化...")
        paths.append(self._chart_volume_change())
        return paths

    def _chart_eps_surprise_table(self) -> Optional[str]:
        """3社のEPS予想/実績/サプライズ%を表形式で表示"""
        try:
            from matplotlib.font_manager import FontProperties
            fp = FontProperties(family=_JP_FONT) if _JP_FONT else None

            data = [self.earnings_data[t] for t in self.tickers]
            n = len(data)

            # レイアウト定数（Y座標の絶対値で管理）
            row_h = 1.0
            title_h = 1.5
            footer_h = 1.0
            total_h = title_h + (n + 1) * row_h + footer_h

            fig, ax = plt.subplots(figsize=(12, max(4.5, total_h * 0.85)), facecolor=SLD_BG)
            ax.set_facecolor(SLD_BG)
            ax.set_xlim(0, 12)
            ax.set_ylim(0, total_h)
            ax.axis("off")

            # タイトル（最上部）
            title_y = total_h - 0.6
            ax.text(6, title_y, "EPSサプライズ — 直近決算ふりかえり",
                    ha="center", fontsize=15, fontweight="bold", color=SLD_DARK,
                    fontproperties=fp if fp else None)
            ax.axhline(title_y - 0.5, color=BRAND_CYAN, linewidth=2.0,
                       xmin=0.02, xmax=0.98)

            # ヘッダー行（タイトル直下）
            cols_x = [0.4, 3.0, 5.0, 7.0, 9.0, 11.0]
            headers = ["銘柄", "決算日", "予想EPS", "実績EPS", "サプライズ", "判定"]
            hdr_y = title_y - 1.2
            ax.add_patch(plt.Rectangle((0.2, hdr_y - 0.4), 11.6, 0.8,
                                        facecolor=SLD_HDR, edgecolor="none", zorder=2))
            for cx, h in zip(cols_x, headers):
                ax.text(cx, hdr_y, h, ha="center", va="center",
                        fontsize=10, fontweight="bold", color=SLD_HDR_FG,
                        fontproperties=fp if fp else None, zorder=3)

            # データ行（ヘッダー直下から下方向へ）
            row_top_y = hdr_y - 0.4  # ヘッダーの下端
            for ri, d in enumerate(data):
                row_bottom = row_top_y - (ri + 1) * row_h
                row_center = row_bottom + row_h / 2
                bg = SLD_ROW if ri % 2 == 0 else SLD_BG
                ax.add_patch(plt.Rectangle((0.2, row_bottom), 11.6, row_h,
                                            facecolor=bg, edgecolor=SLD_RULE,
                                            linewidth=0.5, zorder=1))
                ed_str = d.get("earnings_date").strftime("%m/%d") if d.get("earnings_date") else "-"
                eps_e = d.get("eps_est")
                eps_a = d.get("eps_act")
                surp = d.get("eps_surprise_pct")
                eps_e_s = f"${eps_e:.2f}" if eps_e is not None else "-"
                eps_a_s = f"${eps_a:.2f}" if eps_a is not None else "-"
                surp_s = f"{surp:+.2f}%" if surp is not None else "-"
                # 判定: ▲/▼ で表現（絵文字より確実に表示される）
                if surp is None:
                    judge, judge_color = "—", SLD_TEXT
                elif surp > 5:
                    judge, judge_color = "▲ 大幅ビート", SLD_GRN
                elif surp > 0:
                    judge, judge_color = "▲ ビート", SLD_GRN
                elif surp < -5:
                    judge, judge_color = "▼ 大幅ミス", SLD_RED
                else:
                    judge, judge_color = "▼ ミス", SLD_RED
                surp_color = SLD_GRN if (surp or 0) > 0 else SLD_RED

                vals = [d["ticker"], ed_str, eps_e_s, eps_a_s, surp_s, judge]
                colors = [SLD_DARK, SLD_TEXT, SLD_TEXT, SLD_DARK, surp_color, judge_color]
                weights = ["bold", "normal", "normal", "bold", "bold", "bold"]
                for cx, v, c, w in zip(cols_x, vals, colors, weights):
                    ax.text(cx, row_center, v, ha="center", va="center",
                            fontsize=10, color=c, fontweight=w,
                            fontproperties=fp if fp else None, zorder=3)

            # フッター（最下部）
            footer_y = 0.35
            ax.text(6, footer_y,
                    f"出典: yfinance  ─  集計: {date.today().strftime('%Y/%m/%d')}  ─  Arco Capital Earnings Recap",
                    ha="center", fontsize=8, color=SLD_SUB,
                    fontproperties=fp if fp else None)

            tmp = tempfile.NamedTemporaryFile(suffix="_eps_surprise.png", delete=False)
            tmp.close()
            fig.savefig(tmp.name, dpi=150, facecolor=SLD_BG, bbox_inches="tight")
            plt.close(fig)
            return tmp.name
        except Exception as e:
            print(f"      ⚠️ chart1 エラー: {e}")
            return None

    def _chart_post_earnings_returns(self) -> Optional[str]:
        """決算後の1D/1W/1Mリターンを3社×3期間で棒グラフ"""
        try:
            from matplotlib.font_manager import FontProperties
            fp = FontProperties(family=_JP_FONT) if _JP_FONT else None

            data = [self.earnings_data[t] for t in self.tickers]
            tickers = [d["ticker"] for d in data]
            r1d  = [d.get("ret_1d") or 0 for d in data]
            r1w  = [d.get("ret_1w") or 0 for d in data]
            r1m  = [d.get("ret_1m") or 0 for d in data]

            x = np.arange(len(tickers))
            width = 0.27

            fig, ax = plt.subplots(figsize=(11, 6.5), facecolor=SLD_BG)
            ax.set_facecolor(SLD_BG)
            b1 = ax.bar(x - width, r1d, width, label="1日後", color=SLD_HDR, alpha=0.85, edgecolor=SLD_DARK, linewidth=0.6)
            b2 = ax.bar(x, r1w, width, label="1週間後", color=BRAND_CYAN, alpha=0.85, edgecolor=SLD_DARK, linewidth=0.6)
            b3 = ax.bar(x + width, r1m, width, label="1ヶ月後", color=SLD_GRN, alpha=0.85, edgecolor=SLD_DARK, linewidth=0.6)

            # ラベル
            for bars in (b1, b2, b3):
                for bar in bars:
                    h = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2,
                            h + (0.3 if h >= 0 else -0.3),
                            f"{h:+.1f}%", ha="center",
                            va="bottom" if h >= 0 else "top",
                            fontsize=8.5, fontweight="bold",
                            color=SLD_GRN if h >= 0 else SLD_RED,
                            fontproperties=fp if fp else None)

            ax.axhline(0, color=SLD_DARK, linewidth=0.8)
            ax.set_xticks(x)
            ax.set_xticklabels(tickers, fontsize=11, fontweight="bold", color=SLD_TEXT,
                               fontproperties=fp if fp else None)
            ax.set_ylabel("決算発表後リターン (%)", color=SLD_SUB, fontsize=10,
                          fontproperties=fp if fp else None)
            ax.set_title("決算発表後の株価反応 — 1D / 1W / 1M",
                         color=SLD_DARK, fontsize=14, fontweight="bold",
                         fontproperties=fp if fp else None, pad=14)
            ax.tick_params(colors=SLD_SUB, labelsize=9)
            for s in ax.spines.values(): s.set_color(SLD_RULE)
            ax.grid(color=SLD_RULE, linestyle="--", alpha=0.5, axis="y")
            ax.legend(loc="upper left", fontsize=9, frameon=True,
                      facecolor=SLD_BG, edgecolor=SLD_RULE,
                      prop=fp if fp else None)

            plt.tight_layout()
            tmp = tempfile.NamedTemporaryFile(suffix="_post_returns.png", delete=False)
            tmp.close()
            fig.savefig(tmp.name, dpi=150, facecolor=SLD_BG, bbox_inches="tight")
            plt.close(fig)
            return tmp.name
        except Exception as e:
            print(f"      ⚠️ chart2 エラー: {e}")
            return None

    def _chart_forward_pe_comparison(self) -> Optional[str]:
        """3社のフォワードPE + S&P500中央値（参考線）を比較"""
        try:
            from matplotlib.font_manager import FontProperties
            fp = FontProperties(family=_JP_FONT) if _JP_FONT else None

            data = [self.earnings_data[t] for t in self.tickers]
            tickers = [d["ticker"] for d in data]
            fwd_pes = [d.get("forward_pe") or 0 for d in data]
            tr_pes = [d.get("trailing_pe") or 0 for d in data]

            # S&P500の参考フォワードPE（市場の中央値）— 2026年現在で約20-22
            spy_pe = 21.5

            x = np.arange(len(tickers))
            width = 0.36

            fig, ax = plt.subplots(figsize=(11, 6.5), facecolor=SLD_BG)
            ax.set_facecolor(SLD_BG)

            b1 = ax.bar(x - width/2, fwd_pes, width, label="フォワードPE",
                        color=BRAND_CYAN, alpha=0.85, edgecolor=SLD_DARK, linewidth=0.6)
            b2 = ax.bar(x + width/2, tr_pes, width, label="トレーリングPE",
                        color=SLD_HDR, alpha=0.85, edgecolor=SLD_DARK, linewidth=0.6)

            # 値ラベル
            for bars in (b1, b2):
                for bar in bars:
                    h = bar.get_height()
                    if h <= 0: continue
                    ax.text(bar.get_x() + bar.get_width()/2, h + 0.5,
                            f"{h:.1f}x", ha="center", fontsize=9, fontweight="bold",
                            color=SLD_DARK, fontproperties=fp if fp else None)

            # S&P500参考線
            ax.axhline(spy_pe, color=SLD_ORG, linewidth=1.5, linestyle="--",
                       label=f"S&P500 フォワードPE 参考値 ({spy_pe:.1f}x)")

            ax.set_xticks(x)
            ax.set_xticklabels(tickers, fontsize=11, fontweight="bold", color=SLD_TEXT,
                               fontproperties=fp if fp else None)
            ax.set_ylabel("PE倍率（x）", color=SLD_SUB, fontsize=10,
                          fontproperties=fp if fp else None)
            ax.set_title("バリュエーション比較 — フォワードPE × トレーリングPE",
                         color=SLD_DARK, fontsize=14, fontweight="bold",
                         fontproperties=fp if fp else None, pad=14)
            ax.tick_params(colors=SLD_SUB, labelsize=9)
            for s in ax.spines.values(): s.set_color(SLD_RULE)
            ax.grid(color=SLD_RULE, linestyle="--", alpha=0.5, axis="y")
            ax.legend(loc="upper right", fontsize=9, frameon=True,
                      facecolor=SLD_BG, edgecolor=SLD_RULE,
                      prop=fp if fp else None)

            plt.tight_layout()
            tmp = tempfile.NamedTemporaryFile(suffix="_fwd_pe.png", delete=False)
            tmp.close()
            fig.savefig(tmp.name, dpi=150, facecolor=SLD_BG, bbox_inches="tight")
            plt.close(fig)
            return tmp.name
        except Exception as e:
            print(f"      ⚠️ chart3 エラー: {e}")
            return None

    def _chart_volume_change(self) -> Optional[str]:
        """決算前後20日の出来高推移（3社並べて）"""
        try:
            from matplotlib.font_manager import FontProperties
            fp = FontProperties(family=_JP_FONT) if _JP_FONT else None

            n = len(self.tickers)
            fig, axes = plt.subplots(n, 1, figsize=(12, 2.5 * n + 1), facecolor=SLD_BG)
            if n == 1: axes = [axes]

            for i, t in enumerate(self.tickers):
                d = self.earnings_data[t]
                ax = axes[i]
                ax.set_facecolor(SLD_BG)
                df = d.get("df_3m")
                ed_date = d.get("earnings_date")
                ep = d.get("earnings_pos")
                if df is None or ed_date is None or ep is None:
                    ax.set_visible(False)
                    continue

                df_idx = df.index
                try: df_idx_naive = df_idx.tz_localize(None)
                except Exception: df_idx_naive = df_idx

                # 決算日±20日のウィンドウ
                lo = max(0, ep - 20)
                hi = min(len(df), ep + 21)
                window = df.iloc[lo:hi]
                window_idx = df_idx_naive[lo:hi]
                vols = window["Volume"].values
                colors = []
                for j, idx in enumerate(window_idx):
                    if idx.to_numpy() <= np.datetime64(ed_date):
                        colors.append(SLD_SUB)  # 決算前
                    else:
                        colors.append(BRAND_CYAN)  # 決算後

                ax.bar(range(len(vols)), vols, color=colors, alpha=0.85, edgecolor="none")

                # 決算日マーカー
                marker_pos = ep - lo
                ax.axvline(marker_pos, color=SLD_RED, linewidth=2.0, linestyle="--",
                           label=f"決算日 {ed_date.strftime('%m/%d')}")

                # ラベル
                ax.set_title(f"{t}  ─  出来高推移（決算前後20日）",
                             color=SLD_DARK, fontsize=11, fontweight="bold",
                             fontproperties=fp if fp else None, loc="left", pad=8)
                ax.tick_params(colors=SLD_SUB, labelsize=8, labelbottom=(i == n-1))
                # x軸ラベル: 数日おきに日付
                if i == n - 1:
                    step = max(1, len(window_idx) // 6)
                    xt_pos = list(range(0, len(window_idx), step))
                    xt_lab = [window_idx[k].strftime("%m/%d") for k in xt_pos]
                    ax.set_xticks(xt_pos)
                    ax.set_xticklabels(xt_lab, fontsize=8, color=SLD_SUB,
                                       fontproperties=fp if fp else None)
                ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
                    lambda v, _: f"{v/1e6:.0f}M"))
                for s in ax.spines.values(): s.set_color(SLD_RULE)
                ax.grid(color=SLD_RULE, linestyle="--", alpha=0.4, axis="y")
                ax.legend(loc="upper left", fontsize=8, frameon=True,
                          facecolor=SLD_BG, edgecolor=SLD_RULE,
                          prop=fp if fp else None)

            plt.tight_layout()
            tmp = tempfile.NamedTemporaryFile(suffix="_vol_change.png", delete=False)
            tmp.close()
            fig.savefig(tmp.name, dpi=150, facecolor=SLD_BG, bbox_inches="tight")
            plt.close(fig)
            return tmp.name
        except Exception as e:
            print(f"      ⚠️ chart4 エラー: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4: スレッド原稿生成（5投稿）
    # ─────────────────────────────────────────────────────────────────────────
    def _generate_thread_scripts(self) -> list[dict]:
        import anthropic

        # 全社サマリー文字列を構築
        company_blocks = []
        for t in self.tickers:
            d = self.earnings_data[t]
            block = f"""【{t} ({d.get('name','')[:30]})】
- セクター: {d.get('sector','-')}
- 時価総額: ${d.get('market_cap',0)/1e9:.0f}B
- 決算日: {d.get('earnings_date').strftime('%Y-%m-%d') if d.get('earnings_date') else '-'}
- 予想EPS: ${d.get('eps_est','-') if d.get('eps_est') is None else f"{d.get('eps_est'):.2f}"}
- 実績EPS: ${d.get('eps_act','-') if d.get('eps_act') is None else f"{d.get('eps_act'):.2f}"}
- サプライズ: {d.get('eps_surprise_pct',0):+.2f}%
- 株価反応: 1D={d.get('ret_1d',0) or 0:+.1f}% / 1W={d.get('ret_1w',0) or 0:+.1f}% / 1M={d.get('ret_1m',0) or 0:+.1f}%
- 出来高変化: 決算後/前 = {d.get('volume_ratio',1):.2f}x
- フォワードPE: {d.get('forward_pe','-') if d.get('forward_pe') is None else f"{d.get('forward_pe'):.1f}x"}
- 売上(YoY): {d.get('revenue_yoy', None)}%
- アナリスト推奨: {d.get('recommendation','-')}, 目標株価平均: ${d.get('target_mean','-') if d.get('target_mean') is None else f"{d.get('target_mean'):.2f}"}
"""
            company_blocks.append(block)

        all_companies_data = "\n".join(company_blocks)

        system_prompt = """あなたはArco Capitalのシニアアナリスト兼Xコンテンツ戦略家です。
2026年版Xアルゴリズム（Grok AI統合、リプライ重み75.0、2分以上滞在で最大22倍ブースト）に最適化された米国決算ふりかえりスレッドを制作します。

【絶対ルール（内容）】
- 一次情報（公式決算プレゼン、SEC 10-Q、ガイダンスコメント）を意識した記述
- EPSサプライズ・売上成長・ガイダンス変化の3点を必ず触れる
- 株価反応とファンダメンタルの整合性/非整合性を分析
- 提供されていない数値を創作することは絶対禁止
- 主観的な投資推奨（「買い」「売り」）は避け、観測事実と判断軸を提示

【絶対ルール（人間味20%ブレンド）】
- HOOK と最終投稿には主観的フレーズを1文だけ混ぜる
  例: 「正直、この数字には驚かされた」「個人的には〇〇の動きが特に注目」
- 中間の銘柄解説3投稿は客観分析に徹する

【絶対ルール（リプライ誘発＝スコア75.0獲得）】
最終投稿(index=5)のbody末尾には議論誘発の問いかけを1つ配置:
- 「3社の中で次の決算が最も注目なのはどれですか？」
- 「ガイダンス重視か、実績ビート重視か、皆さんの判断軸は？」
※💬絵文字をつけて独立セクションとする

【絶対ルール（可読性フォーマット）】
body構造:
1. 冒頭1〜2行で指を止めるフック
2. セクションごとに以下マーカーで見出し:
   - 📊 数値・指標
   - ✅ 良かった点
   - ⚠️ 懸念点
   - 📈 株価反応
   - 🎯 ガイダンス・コメンタリー
   - 💬 議論誘発（最終投稿のみ）
3. 中黒(・) または ①②③ で項目列挙
4. セクション間に必ず空行
5. body冒頭に "𝗜𝗡𝗦𝗜𝗚𝗛𝗧..." や罫線を書かない（コード側で自動付与）

【絶対ルール（出力スキーマ）】
JSON配列のみ。各要素のフィールド:
  - "index": 1〜5
  - "role":  "HOOK"/"COMPANY_1"/"COMPANY_2"/"COMPANY_3"/"WRAP_UP"
  - "title": 12〜24字の日本語見出し
  - "body":  本文（目安200〜260字）

【ハッシュタグ】
投稿1(index=1)のbody末尾にのみ、空行1つ空けて:
#決算 #米国株 #投資 #決算速報 #株式投資"""

        user_prompt = f"""今日 {date.today().strftime('%Y年%m月%d日')} 時点で、直近に決算発表された米国大型株3社のふりかえりスレッドを作成してください。
2026年Xアルゴリズム最適化（リプライ誘発 + 滞在時間最大化）で構成。

【対象3社の決算データ】
{all_companies_data}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【5投稿の戦略的役割】

1. HOOK（衝撃型 + 人間味1文） — title例: "今週決算3社の決算ふりかえり"
   - 最初2行で3社のサプライズ%や株価反応を端的に提示（数字の衝撃）
   - 「実績/予想/ガイダンス・株価反応をまとめます」と予告
   - 人間味フレーズを1文（"正直、この3社の決算は明暗が分かれた" 等）
   - body末尾にハッシュタグ（空行1つ空けて）

2. COMPANY_1（{self.tickers[0]} 深掘り） — title例: "{self.tickers[0]}：実績はビート、しかし..."
   - 📊 EPS予想/実績/サプライズ + 売上YoY
   - ✅ 良かった点 / ⚠️ 懸念点
   - 📈 株価反応（1D/1W/1Mを文脈で説明）
   - 🎯 ガイダンス/経営陣コメント（一般的な傾向で推測してOK、断定は避ける）

3. COMPANY_2（{self.tickers[1] if len(self.tickers)>1 else "—"} 深掘り） — 同形式
4. COMPANY_3（{self.tickers[2] if len(self.tickers)>2 else "—"} 深掘り） — 同形式

5. WRAP_UP（総括 + 議論誘発） — title例: "3社の決算が示す市場メッセージ"
   - 共通テーマ（例: 金融セクター強い・テック苦戦 等）を客観的に整理
   - 投資家への示唆（買い推奨ではなく観測ポイント）
   - 人間味フレーズを1文（"自分が最も注目したのは〇〇" 等）
   - 💬 で議論誘発の問いかけを末尾に配置

必ずJSON形式のみで回答してください。"""

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=3500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = msg.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        raw_posts = json.loads(raw)

        posts: list[dict] = []
        total = min(len(raw_posts), 5)
        for i, p in enumerate(raw_posts[:5]):
            idx = int(p.get("index", i + 1))
            role = p.get("role", "")
            title = p.get("title", "").strip()
            body = p.get("body", p.get("text", "")).strip()
            if not title and body:
                first_line = body.split("\n", 1)[0]
                title = first_line.strip("【】 ").strip()
            title = title.split("#")[0].strip()

            # 最終投稿のリプライ誘発を確実化
            if idx == total and idx >= 4:
                body = ensure_discussion_question(body)

            # 投稿1のハッシュタグ
            if idx == 1 and EARNINGS_HASHTAGS not in body:
                body = body.rstrip() + f"\n\n{EARNINGS_HASHTAGS}"

            text = format_post_text(idx, title, body)
            posts.append({"index": idx, "role": role, "title": title, "text": text})
        return posts

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5: X投稿
    # ─────────────────────────────────────────────────────────────────────────
    def _post_thread(self, posts: list[dict], image_paths: list[Optional[str]]) -> str:
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

        first_id = reply_to_id = None
        for i, post in enumerate(posts):
            img = image_paths[i] if i < len(image_paths) else None
            media_ids = None
            if img and Path(img).exists():
                try:
                    m = api_v1.media_upload(filename=img)
                    media_ids = [m.media_id_string]
                    print(f"   📸 メディアアップロード: post {i+1}")
                except Exception as e:
                    print(f"   ⚠️ メディアアップロード失敗: {e}")
            kwargs = {"text": post["text"]}
            if media_ids: kwargs["media_ids"] = media_ids
            if reply_to_id: kwargs["in_reply_to_tweet_id"] = reply_to_id
            response = client_v2.create_tweet(**kwargs)
            tweet_id = response.data["id"]
            print(f"   ✅ 投稿: post {i+1} (id={tweet_id})")
            if first_id is None: first_id = tweet_id
            reply_to_id = tweet_id
            if i < len(posts) - 1:
                time.sleep(2)
        return f"https://x.com/{settings.x_account_handle}/status/{first_id}" if first_id else "（ID取得失敗）"

    # ─────────────────────────────────────────────────────────────────────────
    # 保存
    # ─────────────────────────────────────────────────────────────────────────
    def _save_charts(self, paths: list[Optional[str]]) -> list[Optional[str]]:
        save_dir = (settings.investment_division_dir / "SNS投稿" / "queue" /
                    f"{date.today().isoformat()}_earnings")
        save_dir.mkdir(parents=True, exist_ok=True)
        saved = []
        labels = ["eps_surprise", "post_returns", "fwd_pe", "vol_change"]
        for i, p in enumerate(paths):
            if p and Path(p).exists():
                dest = save_dir / f"{labels[i]}.png"
                shutil.copy2(p, dest)
                saved.append(str(dest))
            else:
                saved.append(None)
        return saved

    def _save_result(self, today: str, posts: list[dict],
                     thread_url: str, saved: list[Optional[str]]) -> str:
        lines = [
            f"# 米国決算ふりかえりスレッド — {today}",
            f"**モード**: {'ドライラン' if self.dry_run else '本番投稿'}",
            f"**取り上げ銘柄**: {', '.join(self.tickers)}",
            f"**スレッドURL**: {thread_url}",
            "",
        ]
        for i, post in enumerate(posts):
            lines += [
                f"## 投稿{post.get('index', i+1)}: {post.get('role','')}",
                post.get("text", ""),
                f"*画像*: `{saved[i]}`" if i < len(saved) and saved[i] else "",
                "",
            ]
        result = "\n".join(lines)
        save_dir = settings.investment_division_dir / "SNS投稿" / "queue"
        save_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{date.today().isoformat()}_earnings_thread.md"
        (save_dir / fname).write_text(result, encoding="utf-8")
        print(f"📄 保存: {save_dir / fname}")
        return result


# ─────────────────────────────────────────────────────────────────────────────
def _ph(title: str) -> None:
    print(f"\n{'='*60}\n  {title}\n{'='*60}\n")


def _preview(posts: list[dict]) -> None:
    print("\n📝 生成されたスレッド原稿:\n" + "-" * 55)
    for p in posts:
        print(f"\n【投稿{p.get('index','?')}: {p.get('role','')}】({len(p.get('text',''))}文字)")
        print(p.get("text", ""))
    print("\n" + "-" * 55 + "\n")


def _cleanup(paths: list[Optional[str]]) -> None:
    for p in paths:
        if p:
            try: Path(p).unlink(missing_ok=True)
            except Exception: pass
