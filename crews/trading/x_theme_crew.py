"""
XThemeThreadCrew — セクター・テーマ型X投稿スレッドクルー（2026年Xアルゴリズム最適化版）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026年版Xアルゴリズム（Grok AI統合）への最適化戦略に基づく6投稿スレッド生成器。

【2026年Xアルゴリズムの最適化原則（Scoring Signal非対称性）】
  - リプライ(75.0) >> リポスト(20.0) >> プロフィールクリック(12.0) >> いいね(1.0)
  - 滞在時間30秒〜2分で1.5倍、2分超で11〜22倍の極大ブースト
  - 外部URL直置きは減点 → 自己リプライ最下層に配置
  - AI的な無機質文章はGrokがスパム判定 → 人間味20%ブレンド必須

【6投稿の戦略的役割】
  投稿1 HOOK(衝撃型):            指を止める強いフック + 人間味1文 + ハッシュタグ
  投稿2 企業背景(特徴列挙型):    銘柄ごとに絵文字見出し + 事業構造解剖
  投稿3 一次情報WHY(EDGAR/決算): 📚 公式文書から読み解く因果関係
  投稿4 クオンツTA(学術根拠型):  📊 SMA×MACD, BB%B, RSI の学術的示唆
  投稿5 フレーミング逆張り:      "90%が見落とす" 構造的リスクの提示
  投稿6 教えてください型シグナル:①②③観測点 + 🔻反転 + 議論誘発の問いかけ

【コンテンツルール】
  - 一次情報（EDGAR 10-K/10-Q、公式決算、学術論文）を明示的に引用
  - 機関投資家レベルのクオンツ視点（シャープレシオ、VIX、バックテスト結果）
  - 断定的煽り禁止。リスクは誠実に開示
  - 数字の創作は絶対禁止
  - 全チャートはmatplotlibで実データから生成（静的画像のみ、動画は使用しない）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

使用例:
    crew = XThemeThreadCrew(theme="semi_us", count=3, dry_run=True)
    crew = XThemeThreadCrew(theme="nikkei", tickers=["9984.T","8035.T"])
"""

import io
import json
import os
import shutil
import tempfile
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import matplotlib.font_manager as _fm
import numpy as np

# 日本語フォント設定
def _setup_jp_font() -> str:
    for path in [
        r"C:\Windows\Fonts\meiryo.ttc",
        r"C:\Windows\Fonts\YuGothM.ttc",
        r"C:\Windows\Fonts\msgothic.ttc",
    ]:
        try:
            from pathlib import Path as _P
            if _P(path).exists():
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

# ブランドカラー
BRAND_DARK  = "#0A0F1E"
BRAND_CYAN  = "#00D4FF"
BRAND_GOLD  = "#FFD700"
BRAND_WHITE = "#FFFFFF"
BRAND_RED   = "#FF4444"
BRAND_GREEN = "#00CC66"

# スライド用カラーパレット（コンサルティングファーム スタイル）
SLD_BG      = "#FFFFFF"      # スライド背景（白）
SLD_DARK    = "#1E2D40"      # ダークネイビー（タイトル・強調）
SLD_TEXT    = "#2C3E50"      # 本文テキスト
SLD_SUB     = "#6B7A8D"      # サブ・キャプション
SLD_RULE    = "#CBD5E1"      # 仕切り線・ボーダー
SLD_ROW     = "#F4F7FA"      # 交互行・カード背景
SLD_HDR     = "#1E3A5F"      # テーブルヘッダー背景
SLD_HDR_FG  = "#FFFFFF"      # テーブルヘッダーテキスト
SLD_GRN     = "#15803D"      # 上昇（緑）
SLD_RED     = "#DC2626"      # 下落（赤）
SLD_ORG     = "#D97706"      # 注意（オレンジ）
SLD_GOLD    = "#B45309"      # アクセント（ゴールド）

HASHTAGS = "#米国株 #投資 #テクニカル分析 #株式投資 #資産運用"

# ═════════════════════════════════════════════════════════════════════════════
# 投稿フォーマット定数 — 全テーマ・全銘柄スレッドで統一したビジュアルに
# ═════════════════════════════════════════════════════════════════════════════
# タイトル太字化: Unicode Mathematical Sans-Serif Bold
BOLD_INSIGHT   = "𝗜𝗡𝗦𝗜𝗚𝗛𝗧"
BOLD_DIGITS    = str.maketrans("0123456789", "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵")
THREAD_DIVIDER = "━━━━━━━━━━━━━━"

# 投稿役割 → デフォルトアイコン（見出し欄に使う補助的な視覚ヒント）
ROLE_ICON = {
    "HOOK": "🚀",
    "企業背景": "🏢", "企業紹介": "🏢",
    "WHY": "🔍", "背景": "🔍", "背景深掘り": "🔍",
    "テクニカル": "📊", "テクニカル分析": "📊",
    "セクター構造": "🧭", "構造": "🧭", "比較": "📊", "全体像": "🧭",
    "注目シグナル": "🎯", "シグナル": "🎯", "戦略": "🎯", "ACTION": "🎯",
}


def format_post_text(index: int, title: str, body: str) -> str:
    """
    投稿テキストを統一フォーマットに整形する。

    出力例:
        𝗜𝗡𝗦𝗜𝗚𝗛𝗧 𝟬𝟭｜【日経注目3銘柄が揃って急伸】
        ━━━━━━━━━━━━━━

        🚀 ソフトバンクG  +7.07%
        ...
    """
    idx_bold = f"{int(index):02d}".translate(BOLD_DIGITS)
    # タイトルは既に【】で括られていれば二重括弧を避ける
    t = title.strip()
    if not (t.startswith("【") and t.endswith("】")):
        t = f"【{t}】"
    header = f"{BOLD_INSIGHT} {idx_bold}｜{t}\n{THREAD_DIVIDER}\n\n"
    return header + body.strip()


# ═════════════════════════════════════════════════════════════════════════════
# 2026年版Xアルゴリズム最適化の戦略定数
# ═════════════════════════════════════════════════════════════════════════════
# 議論誘発質問のフォールバック（最終投稿に問いかけが無い場合に自動付与）
FALLBACK_DISCUSSION_QUESTIONS = [
    "皆さんはこのセクターを今後どう見ていますか？",
    "今後の注目ポイント、皆さんの見解をぜひ教えてください。",
    "ここから上抜けるか調整か、皆さんはどちらに賭けますか？",
    "このシグナル、保有継続か利確か、皆さんはどう判断しますか？",
]
# 議論誘発を示す語彙（これらが最終投稿bodyに含まれていれば「問いかけ済み」と判定）
DISCUSSION_CUES = [
    "？", "?", "皆さん", "どちら", "どう見", "どう判断", "見解", "教えてください",
    "思いますか", "何派", "どっち",
]


def ensure_discussion_question(body: str, cta: str | None = None) -> str:
    """
    最終投稿(index=6)の body に議論誘発の問いかけが含まれているかチェックし、
    不足していれば末尾に追加する。

    Args:
        body: 投稿本文
        cta:  追加する問いかけ文（省略時はフォールバックから選択）

    Returns:
        問いかけ入りの body
    """
    # 議論誘発の語彙が既に含まれていればそのまま返す
    if any(cue in body for cue in DISCUSSION_CUES):
        return body
    # 無ければ末尾に追加
    import random
    q = cta or random.choice(FALLBACK_DISCUSSION_QUESTIONS)
    return body.rstrip() + f"\n\n💬 {q}"


# ═════════════════════════════════════════════════════════════════════════════
# テーマ定義
# ─────────────────────────────────────────────────────────────────────────────
# 各テーマは以下のフィールドを持つ:
#   - name:          表示名
#   - pool:          候補銘柄プール（大きめに用意 / 自動選定の対象）
#   - default_count: 自動選定時のデフォルト銘柄数
#   - min_count:     最小銘柄数（デフォルト 2）
#   - max_count:     最大銘柄数（デフォルト 6）
#   - keywords:      ニュース収集のキーワード
#   - hashtags:      投稿1末尾のハッシュタグ（省略時は既定の米国株タグ）
#   - currency:      "USD"（既定）または "JPY"
#   - names:         ticker → 日本語企業名のマップ
#
# 【後方互換】"tickers" フィールドがある場合は pool が無い場合のフォールバック
#   として使用される。新規テーマは pool を使うこと。
# ═════════════════════════════════════════════════════════════════════════════
THEME_MAP = {
    # ── 米国株セクター細分化 ─────────────────────────────────────────────
    "semi_us": {
        "name": "米国半導体",
        "pool": ["NVDA", "AMD", "TSM", "AVGO", "QCOM", "MU", "INTC",
                 "MRVL", "LRCX", "AMAT", "KLAC", "ASML"],
        "default_count": 3, "min_count": 2, "max_count": 6,
        "keywords": ["semiconductor", "chip", "AI", "GPU"],
        "hashtags": "#半導体 #米国株 #投資 #テクニカル分析 #株式投資",
        "emoji": "🔬", "color": BRAND_CYAN,
        "names": {
            "NVDA": "Nvidia", "AMD": "AMD", "TSM": "TSMC", "AVGO": "Broadcom",
            "QCOM": "Qualcomm", "MU": "Micron", "INTC": "Intel",
            "MRVL": "Marvell", "LRCX": "Lam Research", "AMAT": "Applied Materials",
            "KLAC": "KLA", "ASML": "ASML",
        },
    },
    "ai_infra": {
        "name": "AIインフラ・ハイパースケーラー",
        "pool": ["MSFT", "GOOGL", "META", "AMZN", "ORCL", "CRM", "NVDA", "AVGO"],
        "default_count": 4, "min_count": 3, "max_count": 6,
        "keywords": ["AI", "cloud", "data center", "ChatGPT", "Gemini"],
        "hashtags": "#AI #米国株 #投資 #テクニカル分析 #株式投資",
        "emoji": "🤖", "color": BRAND_GOLD,
        "names": {
            "MSFT": "Microsoft", "GOOGL": "Alphabet", "META": "Meta",
            "AMZN": "Amazon", "ORCL": "Oracle", "CRM": "Salesforce",
            "NVDA": "Nvidia", "AVGO": "Broadcom",
        },
    },
    "materials_us": {
        "name": "米国素材メーカー",
        "pool": ["LIN", "APD", "SHW", "ECL", "FCX", "NEM", "NUE", "VMC",
                 "MLM", "DOW", "PPG", "IFF"],
        "default_count": 3, "min_count": 2, "max_count": 5,
        "keywords": ["materials", "chemicals", "mining", "copper", "industrial"],
        "hashtags": "#素材 #米国株 #投資 #テクニカル分析 #株式投資",
        "emoji": "🏭", "color": "#B45309",
        "names": {
            "LIN": "Linde", "APD": "Air Products", "SHW": "Sherwin-Williams",
            "ECL": "Ecolab", "FCX": "Freeport-McMoRan", "NEM": "Newmont",
            "NUE": "Nucor", "VMC": "Vulcan Materials", "MLM": "Martin Marietta",
            "DOW": "Dow", "PPG": "PPG Industries", "IFF": "IFF",
        },
    },
    "energy_us": {
        "name": "米国エネルギー",
        "pool": ["XOM", "CVX", "COP", "SLB", "OXY", "EOG", "PSX", "MPC", "HES"],
        "default_count": 3, "min_count": 2, "max_count": 5,
        "keywords": ["oil", "energy", "petroleum", "natural gas"],
        "hashtags": "#エネルギー #米国株 #投資 #テクニカル分析 #株式投資",
        "emoji": "⛽", "color": "#166534",
        "names": {
            "XOM": "ExxonMobil", "CVX": "Chevron", "COP": "ConocoPhillips",
            "SLB": "Schlumberger", "OXY": "Occidental", "EOG": "EOG Resources",
            "PSX": "Phillips 66", "MPC": "Marathon Petroleum", "HES": "Hess",
        },
    },
    "financials_us": {
        "name": "米国金融",
        "pool": ["JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW", "USB"],
        "default_count": 3, "min_count": 2, "max_count": 5,
        "keywords": ["bank", "financial", "interest rate", "lending"],
        "hashtags": "#金融 #米国株 #投資 #テクニカル分析 #株式投資",
        "emoji": "🏦", "color": "#1E40AF",
        "names": {
            "JPM": "JPMorgan", "BAC": "Bank of America", "WFC": "Wells Fargo",
            "GS": "Goldman Sachs", "MS": "Morgan Stanley", "C": "Citi",
            "BLK": "BlackRock", "SCHW": "Schwab", "USB": "US Bancorp",
        },
    },
    "fintech": {
        "name": "フィンテック",
        "pool": ["V", "MA", "PYPL", "SQ", "COIN", "HOOD", "SOFI", "AFRM"],
        "default_count": 3, "min_count": 2, "max_count": 5,
        "keywords": ["fintech", "payment", "crypto", "digital banking"],
        "hashtags": "#フィンテック #米国株 #投資 #テクニカル分析 #株式投資",
        "emoji": "💳", "color": "#7C3AED",
        "names": {
            "V": "Visa", "MA": "Mastercard", "PYPL": "PayPal", "SQ": "Block",
            "COIN": "Coinbase", "HOOD": "Robinhood", "SOFI": "SoFi", "AFRM": "Affirm",
        },
    },
    # ── 従来テーマ（pool化 + 既存名維持） ────────────────────────────────
    "quantum": {
        "name": "量子コンピューター",
        "pool": ["QBTS", "IONQ", "QUBT", "RGTI"],  # 小セクターなので全銘柄
        "default_count": 4, "min_count": 2, "max_count": 4,
        "keywords": ["quantum", "quantum computing"],
        "emoji": "⚛️", "color": BRAND_CYAN,
        "names": {
            "QBTS": "D-Wave", "IONQ": "IonQ",
            "QUBT": "Quantum Computing", "RGTI": "Rigetti",
        },
    },
    "ai": {  # 旧名互換: "ai_infra" の別名として残す
        "name": "AI・半導体",
        "pool": ["NVDA", "AMD", "AVGO", "QCOM", "TSM", "MSFT", "GOOGL", "META"],
        "default_count": 4, "min_count": 3, "max_count": 6,
        "keywords": ["artificial intelligence", "AI", "semiconductor", "chip"],
        "emoji": "🤖", "color": BRAND_GOLD,
        "names": {
            "NVDA": "Nvidia", "AMD": "AMD", "AVGO": "Broadcom",
            "QCOM": "Qualcomm", "TSM": "TSMC",
            "MSFT": "Microsoft", "GOOGL": "Alphabet", "META": "Meta",
        },
    },
    "ev": {
        "name": "EV・電気自動車",
        "pool": ["TSLA", "RIVN", "LCID", "NIO", "XPEV", "LI"],
        "default_count": 3, "min_count": 2, "max_count": 5,
        "keywords": ["electric vehicle", "EV", "Tesla"],
        "emoji": "⚡", "color": BRAND_GREEN,
        "names": {
            "TSLA": "Tesla", "RIVN": "Rivian", "LCID": "Lucid",
            "NIO": "NIO", "XPEV": "XPeng", "LI": "Li Auto",
        },
    },
    "nuclear": {
        "name": "原子力・小型原子炉",
        "pool": ["CEG", "VST", "NRG", "SMR", "OKLO"],
        "default_count": 3, "min_count": 2, "max_count": 5,
        "keywords": ["nuclear", "reactor", "SMR", "uranium"],
        "emoji": "☢️", "color": "#FF8C00",
        "names": {
            "CEG": "Constellation", "VST": "Vistra", "NRG": "NRG Energy",
            "SMR": "NuScale", "OKLO": "Oklo",
        },
    },
    # ── 日本株セクター ───────────────────────────────────────────────────
    "nikkei": {
        "name": "日経平均・主要銘柄",
        "pool": ["7203.T", "6758.T", "9984.T", "8035.T",
                 "6861.T", "4063.T", "9433.T", "8306.T", "6501.T"],
        "default_count": 4, "min_count": 3, "max_count": 6,
        "keywords": ["日経平均", "nikkei", "日本株", "東証", "japan stock"],
        "hashtags": "#日経平均 #日本株 #投資 #テクニカル分析 #株式投資",
        "emoji": "🗾", "color": "#E63B2E", "currency": "JPY",
        "names": {
            "7203.T": "トヨタ", "6758.T": "ソニー", "9984.T": "ソフトバンクG",
            "8035.T": "東京エレクトロン", "6861.T": "キーエンス",
            "4063.T": "信越化学", "9433.T": "KDDI",
            "8306.T": "三菱UFJ", "6501.T": "日立製作所",
        },
    },
    "semi_jp": {
        "name": "日本半導体",
        "pool": ["8035.T", "6857.T", "6146.T", "6963.T", "6981.T", "4063.T"],
        "default_count": 3, "min_count": 2, "max_count": 5,
        "keywords": ["半導体", "semiconductor", "日本半導体"],
        "hashtags": "#日本半導体 #日本株 #投資 #テクニカル分析 #株式投資",
        "emoji": "🔬", "color": "#E63B2E", "currency": "JPY",
        "names": {
            "8035.T": "東京エレクトロン", "6857.T": "アドバンテスト",
            "6146.T": "ディスコ", "6963.T": "ローム",
            "6981.T": "村田製作所", "4063.T": "信越化学",
        },
    },
    "materials_jp": {
        "name": "日本素材・化学",
        "pool": ["4063.T", "4005.T", "4183.T", "4188.T", "3402.T", "5401.T",
                 "5713.T", "5020.T"],
        "default_count": 3, "min_count": 2, "max_count": 5,
        "keywords": ["素材", "化学", "chemicals", "materials japan"],
        "hashtags": "#素材 #日本株 #投資 #テクニカル分析 #株式投資",
        "emoji": "🏭", "color": "#E63B2E", "currency": "JPY",
        "names": {
            "4063.T": "信越化学", "4005.T": "住友化学", "4183.T": "三井化学",
            "4188.T": "三菱ケミカル", "3402.T": "東レ",
            "5401.T": "日本製鉄", "5713.T": "住友金属鉱山", "5020.T": "ENEOS",
        },
    },
}


class XThemeThreadCrew:
    """
    セクター・テーマ型X投稿スレッドクルー（動的銘柄選定対応）。

    Args:
        theme:         テーマキー（"semi_us", "materials_us", "nikkei" など）
        tickers:       明示指定する銘柄リスト。指定時は pool 自動選定をスキップ。
        count:         自動選定時の銘柄数（省略時は theme の default_count）。
        selection:     自動選定ロジック:
                       - "movers"  : 変動率の絶対値が大きい順（既定）
                       - "gainers" : 上昇率が大きい順
                       - "losers"  : 下落率が大きい順
                       - "volume"  : 出来高比率が高い順
                       - "rsi"     : RSIが極端な順（過熱/売られすぎ）
                       - "all"     : pool 全銘柄を使用
        dry_run:       True = 投稿せず確認のみ

    使用例:
        # 半導体3銘柄（本日の変動上位を自動選定）
        XThemeThreadCrew(theme="semi_us", count=3, dry_run=True)

        # 素材メーカー（デフォルト3銘柄）
        XThemeThreadCrew(theme="materials_us", dry_run=True)

        # 明示指定
        XThemeThreadCrew(theme="nikkei", tickers=["9984.T", "8035.T"], dry_run=True)

        # 出来高急増トップ3
        XThemeThreadCrew(theme="ai_infra", count=3, selection="volume", dry_run=True)
    """

    def __init__(
        self,
        theme: str = "",
        tickers: list[str] = None,
        count: int | None = None,
        selection: str = "movers",
        dry_run: bool = True,
    ):
        self.theme_key = theme.lower()
        self.theme_def = THEME_MAP.get(self.theme_key, {})
        self.selection = selection.lower() if selection else "movers"

        # 明示tickers指定時はそのまま使用（count/selectionは無視）
        if tickers:
            self.explicit_tickers = [t.upper() if "." not in t else t for t in tickers]
        else:
            self.explicit_tickers = None

        # count決定: 明示指定 > theme default
        self.requested_count = count or self.theme_def.get("default_count", 4)
        self.min_count = self.theme_def.get("min_count", 2)
        self.max_count = self.theme_def.get("max_count", 6)

        # 銘柄プール: 新スキーマ(pool) > 旧スキーマ(tickers) > 空
        self.pool = self.theme_def.get("pool", []) or self.theme_def.get("tickers", [])

        self.theme_name  = self.theme_def.get("name", theme)
        self.theme_color = self.theme_def.get("color", BRAND_CYAN)
        self.hashtags    = self.theme_def.get("hashtags", HASHTAGS)
        self.currency    = self.theme_def.get("currency", "USD")
        self.name_map    = self.theme_def.get("names", {})
        self.dry_run     = dry_run

        # 実際に使用するtickers（run() 実行時に確定）
        self.tickers: list[str] = self.explicit_tickers or []

    def _fmt_price(self, close: float) -> str:
        """通貨に応じた価格フォーマット"""
        if self.currency == "JPY":
            return f"¥{close:,.0f}"
        return f"${close:.2f}"

    def _ticker_label(self, ticker: str) -> str:
        """チャート表示用ラベル: name_map優先 → .T除去フォールバック"""
        if ticker in self.name_map:
            return self.name_map[ticker]
        return ticker.replace(".T", "").replace(".t", "")

    def _ticker_full_label(self, ticker: str) -> str:
        """'企業名 (コード)' 形式: セクターマトリクス等スペースに余裕がある箇所用"""
        code = ticker.replace(".T", "").replace(".t", "")
        if ticker in self.name_map:
            return f"{self.name_map[ticker]}  ({code})"
        return code

    # ─────────────────────────────────────────────────────────────────────────
    def _select_tickers_from_pool(self) -> dict:
        """
        pool から自動選定した銘柄の market_data 辞書を返す。

        ロジック:
        1. 明示tickersがあればそれをfetch
        2. selection="all" なら pool 全銘柄
        3. それ以外は pool 全銘柄をfetchし、selection基準で上位N を選ぶ
        """
        # ── Case 1: 明示指定 ─────────────────────────────────
        if self.explicit_tickers:
            print(f"   → 明示指定された{len(self.explicit_tickers)}銘柄を使用")
            return self._fetch_all(self.explicit_tickers)

        # ── Case 2: pool 全銘柄使用 ─────────────────────────
        if self.selection == "all":
            print(f"   → pool {len(self.pool)}銘柄すべてを使用")
            return self._fetch_all(self.pool)

        # ── Case 3: pool から動的選定 ───────────────────────
        count = max(self.min_count, min(self.requested_count, self.max_count))
        if count >= len(self.pool):
            # 要求数が pool 以上なら全銘柄
            print(f"   → 要求{count}銘柄 >= pool {len(self.pool)}銘柄 → 全銘柄を使用")
            return self._fetch_all(self.pool)

        print(f"   → pool {len(self.pool)}銘柄から「{self.selection}」基準で上位{count}銘柄を選定中...")
        all_data = self._fetch_all(self.pool)
        if not all_data:
            return {}

        # 選定キー
        def sort_key(item):
            t, d = item
            c = d.get("change_pct", 0)
            if self.selection == "gainers":
                return c
            elif self.selection == "losers":
                return -c
            elif self.selection == "volume":
                return d.get("volume_ratio", 0)
            elif self.selection == "rsi":
                rsi = d.get("rsi", 50)
                return abs(rsi - 50)  # 50から離れているほど極端
            else:  # "movers" (既定): 変動率の絶対値
                return abs(c)

        sorted_items = sorted(all_data.items(), key=sort_key, reverse=True)
        selected = dict(sorted_items[:count])
        print(f"   → 選定結果: {', '.join(selected.keys())}")
        return selected

    # ─────────────────────────────────────────────────────────────────────────
    def run(self) -> str:
        today = date.today().strftime("%Y年%m月%d日")
        mode_str = "🔍 ドライラン" if self.dry_run else "🚀 本番投稿モード"
        _ph(f"XThemeThreadCrew 起動 — {today}")
        print(f"  テーマ: {self.theme_name}")
        if self.explicit_tickers:
            print(f"  銘柄: 明示指定 {len(self.explicit_tickers)}銘柄 ({', '.join(self.explicit_tickers)})")
        else:
            print(f"  銘柄: pool {len(self.pool)}銘柄から「{self.selection}」基準で最大{self.requested_count}銘柄を自動選定")
        print(f"  モード: {mode_str}\n")

        print("📊 STEP 1/6: 動的銘柄選定 & データ取得中...\n")
        stocks = self._select_tickers_from_pool()
        # 実際に使用したtickersを記録（_save_result などで参照）
        self.tickers = list(stocks.keys())
        for t, d in stocks.items():
            arrow = "▲" if d["change_pct"] >= 0 else "▼"
            print(f"   {t:<8} {arrow}{abs(d['change_pct']):.2f}%  {self._fmt_price(d['close'])}")
        print()

        print("📰 STEP 2/6: テーマニュース収集中...\n")
        news_items = self._fetch_theme_news(self.tickers, self.theme_def.get("keywords", []))
        print(f"   → {len(news_items)}件取得\n")
        for n in news_items[:3]:
            print(f"   • {n['headline'][:70]}")
        print()

        print("📈 STEP 3/6: チャート生成中...\n")
        chart_paths = self._generate_charts(stocks, news_items)
        print(f"   → {sum(1 for p in chart_paths if p)}枚生成\n")

        print("✍️  STEP 4/6: 台本生成中 (Claude)...\n")
        posts = self._generate_scripts(stocks, news_items)
        _preview(posts)

        if self.dry_run:
            print("📋 STEP 5/6: ドライランのため投稿スキップ\n")
            thread_url = "（ドライラン）"
        else:
            print("🐦 STEP 5/6: X に投稿中...\n")
            thread_url = self._post_thread(posts, chart_paths)

        saved = self._save_images(chart_paths)
        result = self._save_result(today, posts, thread_url, saved)
        _cleanup(chart_paths)

        _ph("XThemeThreadCrew 完了")
        print(f"  スレッドURL: {thread_url}\n")
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: 複数銘柄データ取得
    # ─────────────────────────────────────────────────────────────────────────

    def _fetch_all(self, tickers: list[str]) -> dict:
        import yfinance as yf
        result = {}
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                df = stock.history(period="6mo", interval="1d")
                if df.empty or len(df) < 20:
                    continue
                close     = float(df["Close"].iloc[-1])
                prev      = float(df["Close"].iloc[-2])
                chg       = (close - prev) / prev * 100
                vol       = int(df["Volume"].iloc[-1])
                avg_vol   = int(df["Volume"].tail(20).mean())
                vol_ratio = vol / avg_vol if avg_vol > 0 else 1.0

                # 前週比 (5営業日)
                close_5d_ago = float(df["Close"].iloc[-6]) if len(df) >= 6 else prev
                chg_5d = (close - close_5d_ago) / close_5d_ago * 100

                # RSI(14)
                delta = df["Close"].diff()
                gain  = delta.clip(lower=0).rolling(14).mean()
                loss  = (-delta.clip(upper=0)).rolling(14).mean()
                rsi   = float((100 - 100 / (1 + gain / loss)).iloc[-1])

                # ボリンジャーバンド (20日, ±2σ)
                ma20      = df["Close"].rolling(20).mean()
                std20     = df["Close"].rolling(20).std()
                bb_upper  = float((ma20 + 2 * std20).iloc[-1])
                bb_mid    = float(ma20.iloc[-1])
                bb_lower  = float((ma20 - 2 * std20).iloc[-1])
                bb_width  = (bb_upper - bb_lower) / bb_mid * 100   # バンド幅%
                bb_pct_b  = (close - bb_lower) / (bb_upper - bb_lower) * 100  # %B (0-100)

                # MACD (12-26-9)
                ema12 = df["Close"].ewm(span=12, adjust=False).mean()
                ema26 = df["Close"].ewm(span=26, adjust=False).mean()
                macd_line   = ema12 - ema26
                signal_line = macd_line.ewm(span=9, adjust=False).mean()
                macd_val    = float(macd_line.iloc[-1])
                signal_val  = float(signal_line.iloc[-1])
                macd_hist   = macd_val - signal_val   # ヒストグラム（正=買い勢い）

                # 52週レンジ
                df1y = stock.history(period="1y", interval="1d")
                high52 = float(df1y["High"].max()) if not df1y.empty else float("nan")
                low52  = float(df1y["Low"].min())  if not df1y.empty else float("nan")

                # 会社名
                info = {}
                try:
                    info = stock.info
                except Exception:
                    pass

                result[ticker] = {
                    "ticker": ticker,
                    "name": info.get("longName", ticker),
                    "description": info.get("longBusinessSummary", "")[:300],
                    "sector": info.get("sector", ""),
                    "market_cap": info.get("marketCap", 0),
                    "close": close,
                    "change_pct": chg,
                    "change_5d": chg_5d,
                    "volume": vol,
                    "volume_ratio": vol_ratio,
                    "rsi": rsi,
                    "bb_upper": bb_upper,
                    "bb_mid": bb_mid,
                    "bb_lower": bb_lower,
                    "bb_width": bb_width,
                    "bb_pct_b": bb_pct_b,
                    "macd": macd_val,
                    "macd_signal": signal_val,
                    "macd_hist": macd_hist,
                    "high_52w": high52,
                    "low_52w": low52,
                    "df": df,
                }
            except Exception as e:
                print(f"   ⚠️ {ticker} 取得エラー: {e}")
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: ニュース収集
    # ─────────────────────────────────────────────────────────────────────────

    def _fetch_theme_news(self, tickers: list[str], keywords: list[str]) -> list[dict]:
        import urllib.request
        import xml.etree.ElementTree as ET
        items: list[dict] = []
        seen: set[str] = set()

        def add(headline, summary, source, url=""):
            h = headline.strip()
            if h and h not in seen and len(h) > 10:
                seen.add(h)
                items.append({"headline": h, "summary": summary[:200],
                               "source": source, "url": url})

        # 各銘柄の Yahoo Finance RSS
        for ticker in tickers[:3]:
            try:
                url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    tree = ET.parse(resp)
                for item in tree.iter("item"):
                    title = item.findtext("title") or ""
                    desc  = item.findtext("description") or ""
                    link  = item.findtext("link") or ""
                    add(title, desc, "Yahoo Finance", link)
            except Exception:
                pass

        # Reuters Technology
        try:
            req = urllib.request.Request(
                "https://feeds.reuters.com/reuters/technologyNews",
                headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                tree = ET.parse(resp)
            for item in tree.iter("item"):
                title = item.findtext("title") or ""
                desc  = item.findtext("description") or ""
                kw_match = any(k.lower() in (title + desc).lower() for k in keywords)
                if kw_match:
                    add(title, desc, "Reuters")
        except Exception:
            pass

        return items

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: チャート生成
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_charts(self, stocks: dict, news_items: list[dict]) -> list[Optional[str]]:
        paths: list[Optional[str]] = []

        print("   📊 chart1: ローソク足チャート（グリッド・60日）...")
        paths.append(self._chart_candlestick_grid(stocks))

        print("   📊 chart2: 企業プロファイル（事業説明・業界立ち位置）...")
        paths.append(self._chart_company_profiles(stocks))

        print("   📊 chart3: ビジネス構造スライド（テーマ変動要因）...")
        paths.append(self._chart_theme_why(stocks, news_items))

        print("   📊 chart4: 本日リターン比較（横棒グラフ）...")
        paths.append(self._chart_returns_bar(stocks))

        print("   📊 chart5: セクター銘柄マトリクス...")
        paths.append(self._chart_sector_matrix(stocks))

        print("   📊 chart6: 投資スタンス分類マトリクス...")
        paths.append(self._chart_stance_matrix(stocks))

        return paths

    def _chart_candlestick_grid(self, stocks: dict) -> Optional[str]:
        """各銘柄のローソク足チャート（2x2グリッド・60日）"""
        try:
            from matplotlib.font_manager import FontProperties
            fp = FontProperties(family=_JP_FONT) if _JP_FONT else None

            n = len(stocks)
            ncols = 2
            nrows = (n + ncols - 1) // ncols
            n_days = 60

            fig, axes = plt.subplots(
                nrows, ncols,
                figsize=(14, 4.5 * nrows),
                facecolor=BRAND_DARK,
            )
            # axes を常に 2D リストに統一
            if nrows == 1 and ncols == 1:
                axes = [[axes]]
            elif nrows == 1:
                axes = [list(axes)]
            elif ncols == 1:
                axes = [[ax] for ax in axes]
            else:
                axes = [list(row) for row in axes]

            for idx, (ticker, d) in enumerate(stocks.items()):
                row_i = idx // ncols
                col_i = idx % ncols
                ax = axes[row_i][col_i]
                ax.set_facecolor(BRAND_DARK)

                df = d["df"].tail(n_days).copy()
                if df.empty:
                    ax.set_visible(False)
                    continue

                # ─── ローソク足 ───────────────────────────────────
                for xi, (_, candle) in enumerate(df.iterrows()):
                    o = float(candle["Open"])
                    h = float(candle["High"])
                    l = float(candle["Low"])
                    c = float(candle["Close"])
                    color = BRAND_GREEN if c >= o else BRAND_RED
                    # ひげ（上下）
                    ax.plot([xi, xi], [l, h], color=color,
                            linewidth=0.9, zorder=2)
                    # 胴体
                    body_b = min(o, c)
                    body_h = max(abs(c - o), h * 0.002)  # 最低高さ保証
                    ax.add_patch(plt.Rectangle(
                        (xi - 0.3, body_b), 0.6, body_h,
                        facecolor=color, edgecolor=color,
                        linewidth=0.4, zorder=3,
                    ))

                # ─── x軸: 月単位ラベル ────────────────────────────
                dt_idx = df.index
                seen_m, tick_pos = set(), []
                for xi, dt in enumerate(dt_idx):
                    if hasattr(dt, "month") and dt.month not in seen_m:
                        seen_m.add(dt.month)
                        tick_pos.append(xi)
                ax.set_xticks(tick_pos)
                ax.set_xticklabels(
                    [dt_idx[i].strftime("%Y/%m") for i in tick_pos],
                    color=BRAND_WHITE, fontsize=7,
                    fontproperties=fp if fp else None,
                )

                # ─── サブプロットタイトル ─────────────────────────
                chg = d["change_pct"]
                arrow = "▲" if chg >= 0 else "▼"
                chg_color = BRAND_GREEN if chg >= 0 else BRAND_RED
                ax.set_title(
                    f"{self._ticker_label(ticker)}   {arrow}{abs(chg):.1f}%",
                    color=chg_color, fontsize=11, fontweight="bold",
                    fontproperties=fp if fp else None,
                )
                ax.tick_params(colors=BRAND_WHITE, labelsize=7)
                ax.yaxis.set_tick_params(labelcolor=BRAND_WHITE)
                ax.spines[:].set_color("#333344")
                ax.grid(color="#1A2030", linestyle="--", alpha=0.3)

            # 余分なスロットを非表示
            for idx in range(n, nrows * ncols):
                axes[idx // ncols][idx % ncols].set_visible(False)

            fig.suptitle(
                f"{self.theme_name}  ─  ローソク足チャート（60日）",
                color=self.theme_color, fontsize=13, fontweight="bold",
                fontproperties=fp if fp else None,
                y=1.01,
            )
            plt.tight_layout()

            tmp = tempfile.NamedTemporaryFile(suffix="_theme_chart1.png", delete=False)
            tmp.close()
            fig.savefig(tmp.name, dpi=150, facecolor=BRAND_DARK, bbox_inches="tight")
            plt.close(fig)
            return tmp.name
        except Exception as e:
            print(f"      ⚠️ chart1 エラー: {e}")
            import traceback; traceback.print_exc()
            return None

    def _build_company_profiles(self, stocks: dict) -> list[dict]:
        """Claude Haiku で各銘柄の日本語事業概要・業界立ち位置を生成"""
        import anthropic
        lines = []
        for ticker, d in stocks.items():
            desc = d.get("description", "")[:250]
            name = d.get("name", ticker)
            lines.append(f"{ticker} ({name}): {desc}")

        prompt = f"""以下の企業について投資家向けに日本語で簡潔に説明してください。

{chr(10).join(lines)}

以下のJSON配列のみで返してください（他のテキスト不要）:
[
  {{
    "ticker": "XXXX",
    "name": "会社名（英語でOK）",
    "description": "事業内容を20字以内の日本語で",
    "position": "業界内の立ち位置を15字以内（例: 商用化先行、ソフトウェア特化 など）",
    "type": "技術タイプを10字以内（例: ハードウェア、クラウド など）"
  }}
]"""
        try:
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
            print(f"      ⚠️ 企業プロファイルエラー: {e}")
            return [{"ticker": t, "name": d.get("name", t),
                     "description": "詳細取得中", "position": "—", "type": "—"}
                    for t, d in stocks.items()]

    def _chart_company_profiles(self, stocks: dict) -> Optional[str]:
        """企業プロファイルスライド（事業説明・業界立ち位置カード）— コンサルスタイル白背景"""
        try:
            from matplotlib.font_manager import FontProperties
            fp = FontProperties(family=_JP_FONT) if _JP_FONT else None

            profiles = self._build_company_profiles(stocks)

            def t(ax, x, y, s, **kw):
                kw.setdefault("color", SLD_TEXT)
                kw.setdefault("va", "center")
                if fp:
                    kw["fontproperties"] = fp
                ax.text(x, y, s, **kw)

            fig, ax = plt.subplots(figsize=(12, 8), facecolor=SLD_BG)
            ax.set_facecolor(SLD_BG)
            ax.set_xlim(0, 12)
            ax.set_ylim(0, 11)
            ax.axis("off")

            # タイトルエリア: 上部区切り線 + タイトル
            ax.axhline(10.75, color=self.theme_color, linewidth=2.0,
                       xmin=0.02, xmax=0.98)
            t(ax, 6, 10.5, f"{self.theme_name}  ─  企業プロファイル",
              ha="center", fontsize=17, fontweight="bold",
              color=SLD_DARK)
            t(ax, 6, 9.95,
              f"構成{len(stocks)}銘柄  ─  {date.today().strftime('%Y/%m/%d')}",
              ha="center", fontsize=9, color=SLD_SUB)
            ax.axhline(9.6, color=SLD_RULE, linewidth=0.8,
                       xmin=0.02, xmax=0.98)

            # 時価総額フォーマット
            def fmt_cap(cap):
                if not cap or cap == 0:
                    return "—"
                if self.currency == "JPY":
                    if cap >= 1e12:
                        return f"¥{cap/1e12:.1f}兆"
                    return f"¥{cap/1e8:.0f}億"
                if cap >= 1e12:
                    return f"${cap/1e12:.1f}T"
                if cap >= 1e9:
                    return f"${cap/1e9:.1f}B"
                return f"${cap/1e6:.0f}M"

            # 各銘柄のカード（最大4枚 2x2グリッド）
            n = len(profiles)
            ncols = 2
            nrows = (n + ncols - 1) // ncols

            card_w = 5.4
            card_h = 3.6
            x_starts = [0.3, 6.3]
            y_starts = [9.3 - (row + 1) * (card_h + 0.2) for row in range(nrows)]

            ticker_to_stock = {tk: d for tk, d in stocks.items()}

            for pi, prof in enumerate(profiles[:n]):
                col_i = pi % ncols
                row_i = pi // ncols
                bx = x_starts[col_i]
                by = y_starts[row_i]

                # カード背景: 白 + 細いボーダー
                ax.add_patch(plt.Rectangle(
                    (bx, by), card_w, card_h,
                    facecolor=SLD_BG, edgecolor=SLD_RULE,
                    linewidth=1.2, zorder=2))
                # カードヘッダー帯: ダークネイビー
                ax.add_patch(plt.Rectangle(
                    (bx, by + card_h - 0.7), card_w, 0.7,
                    facecolor=SLD_HDR, zorder=3))

                # ティッカー + 変化率（ヘッダー上、白文字）
                ticker = prof.get("ticker", "")
                stock_d = ticker_to_stock.get(ticker, {})
                chg = stock_d.get("change_pct", 0)
                arrow = "▲" if chg >= 0 else "▼"
                chg_col = SLD_GRN if chg >= 0 else SLD_RED

                t(ax, bx + 0.25, by + card_h - 0.35,
                  self._ticker_full_label(ticker), ha="left", fontsize=12, fontweight="bold",
                  color=SLD_HDR_FG, zorder=4)
                t(ax, bx + card_w - 0.2, by + card_h - 0.35,
                  f"{arrow}{abs(chg):.1f}%", ha="right", fontsize=11,
                  color=chg_col, fontweight="bold", zorder=4)

                # 社名
                name_short = prof.get("name", ticker)[:28]
                t(ax, bx + 0.25, by + card_h - 1.1,
                  name_short, fontsize=8, color=SLD_SUB)

                # 事業概要
                desc = prof.get("description", "")
                t(ax, bx + 0.25, by + card_h - 1.7,
                  desc, fontsize=10, color=SLD_TEXT)

                # 業界立ち位置
                position = prof.get("position", "")
                t(ax, bx + 0.25, by + card_h - 2.25,
                  position, fontsize=9, color=SLD_DARK, fontweight="bold")

                # タイプタグ + 時価総額
                type_tag = prof.get("type", "")
                cap_str = fmt_cap(stock_d.get("market_cap", 0))
                # タイプタグ（SLD_ROW 背景、テーマカラーテキスト）
                ax.add_patch(plt.Rectangle(
                    (bx + 0.2, by + 0.3), len(type_tag) * 0.18 + 0.3, 0.38,
                    facecolor=SLD_ROW, edgecolor=SLD_RULE,
                    linewidth=0.8, zorder=3))
                t(ax, bx + 0.35, by + 0.5,
                  type_tag, fontsize=8, color=self.theme_color)
                # 時価総額（右寄せ）
                t(ax, bx + card_w - 0.2, by + 0.5,
                  f"時価総額 {cap_str}", ha="right",
                  fontsize=8, color=SLD_SUB)

            # フッター
            ax.axhline(0.45, color=SLD_RULE, linewidth=0.5,
                       xmin=0.02, xmax=0.98)
            t(ax, 6, 0.22,
              "Source: yfinance / Anthropic Haiku  ─  Arco Capital",
              ha="center", fontsize=8, color=SLD_SUB)

            tmp = tempfile.NamedTemporaryFile(suffix="_theme_chart2.png", delete=False)
            tmp.close()
            fig.savefig(tmp.name, dpi=150, facecolor=SLD_BG, bbox_inches="tight")
            plt.close(fig)
            return tmp.name
        except Exception as e:
            print(f"      ⚠️ chart2 エラー: {e}")
            import traceback; traceback.print_exc()
            return None

    def _chart_theme_why(self, stocks: dict, news_items: list[dict]) -> Optional[str]:
        """ビジネス構造スライド: テーマ変動要因（3カラム）— コンサルスタイル白背景"""
        try:
            from matplotlib.font_manager import FontProperties
            fp = FontProperties(family=_JP_FONT) if _JP_FONT else None

            # Claude Haiku で日本語3視点要約
            summaries = self._build_why_summaries(stocks, news_items)

            def t(ax, x, y, s, **kw):
                kw.setdefault("color", SLD_TEXT)
                kw.setdefault("va", "center")
                if fp:
                    kw["fontproperties"] = fp
                ax.text(x, y, s, **kw)

            # ─── レイアウト定数 ─────────────────────────────
            TITLE_TOP   = 9.4   # タイトルテキスト y
            RULE1_Y     = 9.1   # テーマカラー区切り線
            SUB_Y       = 8.75  # サブタイトルテキスト
            RULE2_Y     = 8.45  # サブタイトル下の区切り線
            BW, BH      = 3.5, 4.5
            BY          = RULE2_Y - BH - 0.2   # = 3.75

            # フッターはボックス直下に配置（空白ゼロ）
            FOOTER_RULE = BY - 0.35
            FOOTER_SRC  = BY - 0.80
            FOOTER_BRD  = BY - 1.30
            Y_MIN       = BY - 1.55            # ylim下端

            # figsize を ylim 範囲に合わせて縮小
            y_range  = TITLE_TOP + 0.7 - Y_MIN   # 描画範囲 (units)
            fig_h    = max(4.0, y_range * 0.65)

            fig, ax = plt.subplots(figsize=(12, fig_h), facecolor=SLD_BG)
            ax.set_facecolor(SLD_BG)
            ax.set_xlim(0, 12)
            ax.set_ylim(Y_MIN, TITLE_TOP + 0.7)
            ax.axis("off")

            # 代表銘柄の変化率
            best = max(stocks.values(), key=lambda d: abs(d["change_pct"]))
            chg = best["change_pct"]
            arrow = "▲" if chg >= 0 else "▼"
            chg_color = SLD_GRN if chg >= 0 else SLD_RED

            # タイトル + タイトル下の区切り線（テーマカラー）
            t(ax, 6, TITLE_TOP, f"{self.theme_name}  急騰要因分析",
              ha="center", fontsize=17, fontweight="bold",
              color=SLD_DARK)
            ax.axhline(RULE1_Y, color=self.theme_color, linewidth=2.0,
                       xmin=0.02, xmax=0.98)
            best_ticker = best["ticker"]
            best_label = self._ticker_label(best_ticker)
            t(ax, 6, SUB_Y,
              f"筆頭: {best_label} {arrow}{abs(chg):.1f}%  ─  "
              f"銘柄数: {len(stocks)}  ─  {date.today().strftime('%Y/%m/%d')}",
              ha="center", fontsize=10, color=SLD_SUB)
            ax.axhline(RULE2_Y, color=SLD_RULE, linewidth=0.8,
                       xmin=0.02, xmax=0.98)

            # カラムヘッダーカラー: 主因=SLD_GRN、背景=SLD_ORG、展望=SLD_HDR
            col_header_colors = [SLD_GRN, SLD_ORG, SLD_HDR]
            box_left = [0.25, 4.25, 8.25]

            for col, (bl, item) in enumerate(zip(box_left, summaries)):
                by = BY
                bw, bh = BW, BH
                # カラム背景: 白 + ボーダー
                ax.add_patch(plt.Rectangle(
                    (bl, by), bw, bh, facecolor=SLD_BG,
                    edgecolor=SLD_RULE, linewidth=1.2, zorder=2))
                # カラムヘッダー帯（高め: 0.75）
                ax.add_patch(plt.Rectangle(
                    (bl, by + bh - 0.75), bw, 0.75,
                    facecolor=col_header_colors[col], zorder=3))
                t(ax, bl + bw / 2, by + bh - 0.38,
                  item.get("angle", ""),
                  ha="center", fontsize=12, fontweight="bold",
                  color=SLD_HDR_FG, zorder=4)

                # ソース名
                src = item.get("source", "").split(" - ")[0].split("/")[0].strip()[:16]
                t(ax, bl + 0.25, by + bh - 1.15, f"[ {src} ]",
                  fontsize=8, color=SLD_SUB)

                # 区切り線（ソース下）
                ax.axhline(by + bh - 1.38, color=SLD_RULE, linewidth=0.6,
                           xmin=(bl + 0.05) / 12, xmax=(bl + bw - 0.05) / 12)

                # bullets 表示（最大2つ、折り返しあり）
                bullets = item.get("bullets", [item.get("summary", "")])
                bullet_y_start = by + bh - 1.85
                bullet_spacing = 1.15
                max_line_chars  = 11   # 列幅に収まる日本語文字数上限
                for bi, bullet in enumerate(bullets[:2]):
                    raw = str(bullet)
                    # max_line_chars 字ごとに折り返し
                    sub_lines = [raw[i:i+max_line_chars]
                                 for i in range(0, min(len(raw), max_line_chars*2), max_line_chars)]
                    by_dot = bullet_y_start - bi * bullet_spacing
                    dot = plt.Circle(
                        (bl + 0.28, by_dot + 0.05 * (len(sub_lines)-1)),
                        0.055, color=col_header_colors[col], zorder=4)
                    ax.add_patch(dot)
                    for si, sl in enumerate(sub_lines[:2]):
                        t(ax, bl + 0.48, by_dot - si * 0.52,
                          sl, fontsize=9, color=SLD_TEXT, va="center")

            # フッター区切り線 + Source行（ボックス直下）
            ax.axhline(FOOTER_RULE, color=SLD_RULE, linewidth=0.5,
                       xmin=0.02, xmax=0.98)
            used = list(dict.fromkeys(s.get("source","").split("-")[0].strip()
                                      for s in summaries if s.get("source")))
            t(ax, 6, FOOTER_SRC,
              f"Source: {' / '.join(used)}  ─  {date.today().strftime('%Y/%m/%d')}",
              ha="center", fontsize=8, color=SLD_SUB)
            t(ax, 6, FOOTER_BRD, "Arco Capital — 資産運用事業部",
              ha="center", fontsize=8, color=SLD_SUB, fontweight="bold")

            tmp = tempfile.NamedTemporaryFile(
                suffix="_theme_chart3.png", delete=False)
            tmp.close()
            fig.savefig(tmp.name, dpi=150, facecolor=SLD_BG,
                        bbox_inches="tight")
            plt.close(fig)
            return tmp.name
        except Exception as e:
            print(f"      ⚠️ chart3 エラー: {e}")
            return None

    def _build_why_summaries(self, stocks: dict, news_items: list[dict]) -> list[dict]:
        """Claude Haiku で日本語3視点サマリーを生成"""
        import anthropic
        news_text = "\n".join(
            f"- [{n['source']}] {n['headline']}" for n in news_items[:10])
        best = max(stocks.values(), key=lambda d: abs(d["change_pct"]))

        prompt = f"""テーマ「{self.theme_name}」関連株が本日急騰しました。
主要銘柄: {', '.join(f"{t} {d['change_pct']:+.1f}%" for t,d in stocks.items())}

ニュース:
{news_text}

以下のJSON形式のみで返してください（他のテキスト不要）:
[
  {{
    "angle": "主因",
    "bullets": ["直接トリガーを18字以内で", "補足ポイントを18字以内で"],
    "source": "情報源名"
  }},
  {{
    "angle": "背景",
    "bullets": ["市場背景を18字以内で", "補足ポイントを18字以内で"],
    "source": "情報源名"
  }},
  {{
    "angle": "展望",
    "bullets": ["今後の注目点を18字以内で", "リスク要因を18字以内で"],
    "source": "テクニカル分析"
  }}
]

重要: bullets の各要素は必ず純粋な日本語18字以内。英単語が必要な場合はカタカナ表記にすること（例: Nvidia→エヌビディア、RSI→RSI）。"""
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
            print(f"      ⚠️ WHY要約エラー: {e}")
            return [
                {"angle": "主因", "summary": "急騰の直接要因", "source": "Yahoo Finance"},
                {"angle": "背景", "summary": "市場全体の地合い", "source": "Reuters"},
                {"angle": "展望", "summary": "今後の注目点", "source": "テクニカル分析"},
            ]

    def _chart_returns_bar(self, stocks: dict) -> Optional[str]:
        """本日リターン横棒グラフ — コンサルスタイル白背景"""
        try:
            from matplotlib.font_manager import FontProperties
            fp = FontProperties(family=_JP_FONT) if _JP_FONT else None

            tickers = list(stocks.keys())
            returns = [stocks[t]["change_pct"] for t in tickers]
            sorted_pairs = sorted(zip(returns, tickers))   # 昇順（上が最大）
            sorted_ret, sorted_tickers = zip(*sorted_pairs)

            n = len(sorted_tickers)
            fig_h = max(3.5, 1.1 * n + 1.8)
            fig, ax = plt.subplots(figsize=(10, fig_h), facecolor=SLD_BG)
            ax.set_facecolor(SLD_BG)

            # バーカラー: 上昇=SLD_GRN, 下落=SLD_RED
            bar_colors = [SLD_GRN if r >= 0 else SLD_RED for r in sorted_ret]
            y_pos = np.arange(n)

            bars = ax.barh(y_pos, sorted_ret, color=bar_colors,
                           alpha=0.85, height=0.55)

            # 値ラベル（バー右端 or 左端）
            for bar, val in zip(bars, sorted_ret):
                offset = abs(max(sorted_ret, key=abs)) * 0.02
                x_pos = val + (offset if val >= 0 else -offset)
                ha = "left" if val >= 0 else "right"
                arrow = "▲" if val >= 0 else "▼"
                label_color = SLD_GRN if val >= 0 else SLD_RED
                ax.text(x_pos, bar.get_y() + bar.get_height() / 2,
                        f"{arrow}{abs(val):.1f}%",
                        va="center", ha=ha, color=label_color,
                        fontsize=10, fontweight="bold",
                        fontproperties=fp if fp else None)

            ax.set_yticks(y_pos)
            ax.set_yticklabels([self._ticker_label(t) for t in sorted_tickers],
                               color=SLD_TEXT, fontsize=12,
                               fontweight="bold",
                               fontproperties=fp if fp else None)
            ax.set_xlabel("本日変化率 (%)", color=SLD_SUB, fontsize=9,
                          fontproperties=fp if fp else None)
            ax.set_title(f"{self.theme_name}  ─  本日リターン比較",
                         color=SLD_DARK, fontsize=13, fontweight="bold",
                         fontproperties=fp if fp else None, pad=14)
            ax.axvline(0, color=SLD_RULE, linewidth=1.0)
            ax.tick_params(colors=SLD_SUB, labelsize=9)
            for spine in ax.spines.values():
                spine.set_color(SLD_RULE)
            ax.grid(color=SLD_RULE, linestyle="--", alpha=0.6, axis="x")

            # タイトル下アクセントライン
            ax.set_title(f"{self.theme_name}  ─  本日リターン比較",
                         color=SLD_DARK, fontsize=13, fontweight="bold",
                         fontproperties=fp if fp else None, pad=14)

            plt.tight_layout()
            tmp = tempfile.NamedTemporaryFile(
                suffix="_theme_chart4.png", delete=False)
            tmp.close()
            fig.savefig(tmp.name, dpi=150, facecolor=SLD_BG,
                        bbox_inches="tight")
            plt.close(fig)
            return tmp.name
        except Exception as e:
            print(f"      ⚠️ chart4 エラー: {e}")
            return None

    def _chart_sector_matrix(self, stocks: dict) -> Optional[str]:
        """セクター銘柄マトリクス（指標一覧テーブル）— コンサルスタイル白背景"""
        try:
            from matplotlib.font_manager import FontProperties
            fp = FontProperties(family=_JP_FONT) if _JP_FONT else None

            def t(ax, x, y, s, **kw):
                kw.setdefault("color", SLD_TEXT)
                kw.setdefault("va", "center")
                if fp:
                    kw["fontproperties"] = fp
                ax.text(x, y, s, **kw)

            n_stocks = len(stocks)
            row_h    = 0.9
            hdr_h    = 0.65
            TITLE_H  = 1.6   # タイトル+ライン+余白
            FOOTER_H = 0.8

            total_h = TITLE_H + hdr_h + row_h * n_stocks + FOOTER_H
            fig_h   = max(3.5, total_h * 0.72)

            fig, ax = plt.subplots(figsize=(12, fig_h), facecolor=SLD_BG)
            ax.set_facecolor(SLD_BG)
            ax.set_xlim(0, 12)
            ax.set_ylim(0, total_h)
            ax.axis("off")

            # 位置を上から順に計算
            title_y  = total_h - 0.65           # タイトルテキスト
            line_y   = total_h - TITLE_H + 0.25 # テーマカラー区切り線
            hdr_y    = line_y - 0.35            # ヘッダー行の下端

            t(ax, 6, title_y, f"{self.theme_name}  ─  銘柄指標マトリクス",
              ha="center", fontsize=16, fontweight="bold",
              color=SLD_DARK)
            ax.axhline(line_y, color=self.theme_color, linewidth=2.0,
                       xmin=0.02, xmax=0.98)

            # ─── レイアウト定数 ───────────────────────────────────────
            # 第1列（銘柄名）を広めに確保
            cols_x   = [0.35, 3.2, 4.9, 6.5, 8.1, 10.0]
            headers  = ["銘柄", "終値", "本日変化率", "RSI(14)", "出来高比", "52W高値比"]

            # ─── ヘッダー行 ─────────────────────────────────────────
            ax.add_patch(plt.Rectangle(
                (0.2, hdr_y), 11.6, hdr_h,
                facecolor=SLD_HDR, edgecolor="none", linewidth=0, zorder=2))
            for cx, h in zip(cols_x, headers):
                t(ax, cx, hdr_y + hdr_h / 2, h,
                  fontsize=9, fontweight="bold", color=SLD_HDR_FG, zorder=3)

            # ─── データ行（ヘッダー下から開始・重複なし）──────────────
            for ri, (ticker, d) in enumerate(stocks.items()):
                row_bottom = hdr_y - row_h * (ri + 1)
                row_text_y = row_bottom + row_h / 2
                chg        = d["change_pct"]
                chg_color  = SLD_GRN if chg >= 0 else SLD_RED
                arrow      = "▲" if chg >= 0 else "▼"

                # 交互背景
                bg_col = SLD_BG if ri % 2 == 0 else SLD_ROW
                ax.add_patch(plt.Rectangle(
                    (0.2, row_bottom), 11.6, row_h,
                    facecolor=bg_col, edgecolor=SLD_RULE, linewidth=0.4, zorder=1))

                # 52週高値比
                if not np.isnan(d["high_52w"]) and d["high_52w"] > 0:
                    from_high = (d["close"] - d["high_52w"]) / d["high_52w"] * 100
                    from_high_str = f"{from_high:+.1f}%"
                else:
                    from_high_str = "—"

                rsi_val = d["rsi"]
                vol_ratio = d["volume_ratio"]
                vals = [
                    self._ticker_label(ticker),   # 社名のみ（列幅節約）
                    self._fmt_price(d["close"]),
                    f"{arrow}{abs(chg):.1f}%",
                    f"{rsi_val:.0f}",
                    f"{vol_ratio:.1f}x",
                    from_high_str,
                ]
                val_colors = [
                    SLD_DARK,
                    SLD_TEXT,
                    chg_color,
                    (SLD_RED if rsi_val > 70 else SLD_GRN if rsi_val < 30 else SLD_TEXT),
                    (SLD_ORG if vol_ratio > 2.0 else SLD_TEXT),
                    (SLD_RED if from_high_str.startswith("-") else SLD_GRN if from_high_str.startswith("+") else SLD_TEXT),
                ]
                val_weights = ["bold", "normal", "bold", "bold", "bold", "normal"]
                for cx, val, vc, vw in zip(cols_x, vals, val_colors, val_weights):
                    t(ax, cx, row_text_y, val, fontsize=10, color=vc, fontweight=vw, zorder=3)

            # 下区切り線 + フッター（最終行のすぐ下）
            last_bottom = hdr_y - row_h * n_stocks
            ax.axhline(last_bottom, color=SLD_RULE, linewidth=0.8,
                       xmin=0.02, xmax=0.98)
            footer_text_y = last_bottom - 0.45
            t(ax, 6, footer_text_y,
              f"Data: yfinance  ─  {date.today().strftime('%Y/%m/%d')}  Arco Capital",
              ha="center", fontsize=8, color=SLD_SUB)

            # ylim を実際のコンテンツ範囲だけに絞る（下部空白を排除）
            ax.set_ylim(footer_text_y - 0.15, total_h)

            tmp = tempfile.NamedTemporaryFile(
                suffix="_theme_chart5.png", delete=False)
            tmp.close()
            fig.savefig(tmp.name, dpi=150, facecolor=SLD_BG,
                        bbox_inches="tight")
            plt.close(fig)
            return tmp.name
        except Exception as e:
            print(f"      ⚠️ chart5 エラー: {e}")
            return None

    def _chart_stance_matrix(self, stocks: dict) -> Optional[str]:
        """投資スタンス分類マトリクス（ハイリスク vs 低リスク）— コンサルスタイル白背景"""
        try:
            from matplotlib.font_manager import FontProperties
            fp = FontProperties(family=_JP_FONT) if _JP_FONT else None

            def t(ax, x, y, s, **kw):
                kw.setdefault("color", SLD_TEXT)
                kw.setdefault("va", "center")
                if fp:
                    kw["fontproperties"] = fp
                ax.text(x, y, s, **kw)

            fig, ax = plt.subplots(figsize=(12, 7), facecolor=SLD_BG)
            ax.set_facecolor(SLD_BG)
            ax.set_xlim(0, 12)
            ax.set_ylim(0, 10)
            ax.axis("off")

            # タイトル: SLD_DARK（金色から変更）
            t(ax, 6, 9.4, f"{self.theme_name}  ─  投資スタンス分類",
              ha="center", fontsize=16, fontweight="bold", color=SLD_DARK)
            ax.axhline(9.05, color=self.theme_color, linewidth=2.0,
                       xmin=0.02, xmax=0.98)
            ax.axhline(9.0, color=SLD_RULE, linewidth=0.6,
                       xmin=0.02, xmax=0.98)

            # 4象限: 上昇率 × RSI でポジショニング
            # 各象限: (背景色, ボーダー色, ラベルカラー)
            quadrants = [
                {
                    "label": "強気・過熱",     "x": 6.3, "y": 5.0,
                    "bg": "#FEF2F2", "border": SLD_RED, "label_color": SLD_RED,
                    "desc": "RSI高く上昇済\n利確検討圏",
                    "cond": lambda d: d["rsi"] > 65 and d["change_pct"] > 0,
                },
                {
                    "label": "強気・余地あり",  "x": 0.3, "y": 5.0,
                    "bg": "#F0FDF4", "border": SLD_GRN, "label_color": SLD_GRN,
                    "desc": "上昇しつつ\nRSI中立で追撃余地",
                    "cond": lambda d: d["rsi"] <= 65 and d["change_pct"] > 0,
                },
                {
                    "label": "弱気・売られすぎ", "x": 0.3, "y": 2.0,
                    "bg": "#EFF6FF", "border": "#2563EB", "label_color": "#2563EB",
                    "desc": "下落しつつ\nRSI低く逆張り検討",
                    "cond": lambda d: d["rsi"] < 40 and d["change_pct"] <= 0,
                },
                {
                    "label": "弱気・継続注意",  "x": 6.3, "y": 2.0,
                    "bg": "#FFF7ED", "border": SLD_ORG, "label_color": SLD_ORG,
                    "desc": "下落かつ\nRSI中立で戻り待ち",
                    "cond": lambda d: d["rsi"] >= 40 and d["change_pct"] <= 0,
                },
            ]

            for q in quadrants:
                qx, qy, qw, qh = q["x"], q["y"], 5.4, 2.8
                # 象限背景
                ax.add_patch(plt.Rectangle(
                    (qx, qy), qw, qh,
                    facecolor=q["bg"], edgecolor=q["border"],
                    linewidth=1.8, zorder=2))

                # 象限ラベル（上部帯）
                ax.add_patch(plt.Rectangle(
                    (qx, qy + qh - 0.58), qw, 0.58,
                    facecolor=q["border"], alpha=0.15,
                    edgecolor="none", zorder=3))
                t(ax, qx + 0.2, qy + qh - 0.29, q["label"],
                  fontsize=10, fontweight="bold", color=q["label_color"], zorder=4)

                # 該当銘柄（各銘柄を1行ずつ、RSI・変化率付き）
                matched = [(tk, d) for tk, d in stocks.items() if q["cond"](d)]
                # 説明テキストエリアの高さを確保（下部0.9固定）
                desc_reserve = 0.9
                stock_area_h = qh - 0.58 - desc_reserve  # ラベル帯(0.58) + 説明(0.9)
                max_stocks   = max(1, int(stock_area_h / 0.52))

                if matched:
                    spacing = min(0.52, stock_area_h / len(matched))
                    for mi, (tk, d) in enumerate(matched[:max_stocks]):
                        chg   = d["change_pct"]
                        arrow = "▲" if chg >= 0 else "▼"
                        c     = SLD_GRN if chg >= 0 else SLD_RED
                        iy    = qy + qh - 1.0 - mi * spacing
                        line  = f"{self._ticker_label(tk)}  {arrow}{abs(chg):.1f}%  RSI:{d['rsi']:.0f}"
                        dot = plt.Circle((qx + 0.2, iy), 0.07, color=c, zorder=5)
                        ax.add_patch(dot)
                        t(ax, qx + 0.35, iy,
                          line, fontsize=9.5, color=SLD_DARK, fontweight="bold", zorder=4)
                else:
                    t(ax, qx + qw / 2, qy + qh / 2, "該当銘柄なし",
                      ha="center", fontsize=10, color=SLD_SUB, style="italic", zorder=4)

                # 説明テキスト（下部・固定エリア）
                ax.axhline(qy + desc_reserve - 0.05, color=q["border"],
                           linewidth=0.5, alpha=0.4,
                           xmin=qx / 12, xmax=(qx + qw) / 12)
                for li, line in enumerate(q["desc"].split("\n")):
                    t(ax, qx + 0.25, qy + desc_reserve - 0.28 - li * 0.3,
                      line, fontsize=8, color=SLD_SUB, zorder=4)

            # 中央の分割線（SLD_RULE、点線）
            ax.axhline(5.0, color=SLD_RULE, linewidth=1.2,
                       xmin=0.02, xmax=0.98, linestyle="--")
            ax.axvline(6.0, color=SLD_RULE, linewidth=1.2,
                       ymin=0.18, ymax=0.92, linestyle="--")
            t(ax, 6.0, 5.25, "RSI 65", ha="center",
              fontsize=8, color=SLD_SUB)

            # 軸ラベル（SLD_SUB）
            t(ax, 6, 8.75, "RSI 高い（過熱）  →",
              ha="center", fontsize=8, color=SLD_SUB)
            t(ax, 1.0, 8.55, "▲ 上昇",  fontsize=9, color=SLD_GRN, fontweight="bold")
            t(ax, 1.0, 1.75, "▼ 下落",  fontsize=9, color=SLD_RED, fontweight="bold")

            ax.axhline(0.7, color=SLD_RULE, linewidth=0.5,
                       xmin=0.02, xmax=0.98)
            t(ax, 6, 0.35,
              f"RSI・本日変化率による分類  ─  {date.today().strftime('%Y/%m/%d')}  Arco Capital",
              ha="center", fontsize=8, color=SLD_SUB)

            tmp = tempfile.NamedTemporaryFile(
                suffix="_theme_chart6.png", delete=False)
            tmp.close()
            fig.savefig(tmp.name, dpi=150, facecolor=SLD_BG,
                        bbox_inches="tight")
            plt.close(fig)
            return tmp.name
        except Exception as e:
            print(f"      ⚠️ chart6 エラー: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4: 台本生成
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_scripts(self, stocks: dict, news_items: list[dict]) -> list[dict]:
        import anthropic

        today = date.today().strftime("%Y年%m月%d日")

        # ─── テクニカル詳細サマリー（銘柄ごと）──────────────────────────
        tech_lines = []
        for t, d in stocks.items():
            label = self._ticker_label(t)
            bb_pos = (
                "上限バンド付近（過熱シグナル）" if d["bb_pct_b"] > 85
                else "下限バンド付近（売られすぎ）" if d["bb_pct_b"] < 15
                else f"バンド内 %B={d['bb_pct_b']:.0f}"
            )
            macd_trend = "ゴールデンクロス直後" if d["macd_hist"] > 0 and d["macd"] > 0 else \
                         "デッドクロス直後" if d["macd_hist"] < 0 and d["macd"] < 0 else \
                         "MACDプラス圏" if d["macd_hist"] > 0 else "MACDマイナス圏"
            tech_lines.append(
                f"【{label}】"
                f" 当日変化率:{d['change_pct']:+.2f}%  5日比:{d['change_5d']:+.2f}%"
                f" | RSI(14):{d['rsi']:.1f}"
                f" | BB %B:{d['bb_pct_b']:.0f}（{bb_pos}）"
                f"  BBバンド幅:{d['bb_width']:.1f}%"
                f" | MACD:{d['macd']:.3f}  Signal:{d['macd_signal']:.3f}  Hist:{d['macd_hist']:+.3f}（{macd_trend}）"
                f" | 出来高比:{d['volume_ratio']:.1f}x"
            )
        stocks_summary = "\n".join(tech_lines)

        news_text = "\n".join(
            f"- [{n['source']}] {n['headline']}" for n in news_items[:10]
        ) or "ニュースなし"

        system_prompt = f"""あなたはArco Capitalのシニアアナリスト兼Xコンテンツ戦略家です。
2026年版Xアルゴリズム（Grok AI統合、Rust基盤、6000特徴量の本ランキング）に完全最適化された米国株・日本株セクター分析スレッドを制作します。

【2026年Xアルゴリズム最適化原則】
- Scoring Signal: リプライ(75.0) >> リポスト(20.0) >> プロフィールクリック(12.0) >> いいね(1.0)
- 滞在時間 30秒〜2分で1.5倍、2分超で11〜22倍の極大ブースト
  → 図解・データ密度・論理構造で熟読時間を設計する
- Grokのスパム判定を回避するため、無機質なAI文章ではなく「人間らしい主観や体験」を20%ブレンドする
- 外部URLは投稿本文に置かない（減点対象）

【絶対ルール（内容の深さ）】
- 一次情報（EDGAR 10-K/10-Q、公式決算、学術論文）を可能な限り具体的に引用する
- 機関投資家レベルのクオンツ視点で語る（シャープレシオ、バックテスト、VIX、%B、MACDヒスト）
- 提供されていない数値を創作することは絶対禁止
- 「なぜそうなっているか」の因果関係を常に明示する
- 断定的煽り（「爆上げ確実」等）は禁止。リスクファクターも誠実に開示

【絶対ルール（人間味20%ブレンド）】
以下の投稿には主観的フレーズを必ず1文だけ混ぜる:
- HOOK(投稿1): 「正直、この動きは予想外だった」「個人的には今週のビッグサプライズ」「素直にこれは興奮する動き」等
- 注目シグナル(投稿6): 「自分が最も注視しているのは〇〇」「これは見逃したくないサイン」等
※他の投稿(2〜5)は客観分析に徹する

【絶対ルール（リプライ誘発＝スコア75.0獲得）】
最終投稿(index=6)のbody末尾には必ず議論誘発の問いかけを1つ配置する:
- 「皆さんはこのセクターをどう見ていますか？」
- 「A銘柄とB銘柄、今後5年でどちらが勝つと思いますか？」
- 「〇〇派の方、ぜひコメントで意見を教えてください」
※問いかけは💬絵文字をつけて独立セクションとする

【絶対ルール（可読性フォーマット）】
body構造:
1. 冒頭1〜2行で指を止めるフック（数字の衝撃 or 意外性 or 問題提起）
2. セクションごとに以下マーカーで見出し:
   - ▼ / ▶   単純項目・ポイント
   - ⚠️       注意・リスク
   - 🔻       下落・反転シグナル
   - 📊       データ・指標
   - 📚       一次情報引用（EDGAR/決算資料/論文）
   - 💬       議論誘発の問いかけ
3. 中黒(・)+全角スペース で項目列挙、または ①②③ で分岐整理
4. セクション間に必ず空行
5. 銘柄リストは「絵文字 半角スペース 銘柄名 +X.XX%」で縦並び
6. body冒頭に "𝗜𝗡𝗦𝗜𝗚𝗛𝗧..." や罫線は書かない（コード側で自動付与）

【絶対ルール（出力スキーマ）】
JSON配列のみ。各要素のフィールド:
  - "index": 1〜6 の整数
  - "role":  "HOOK"/"企業背景"/"WHY"/"テクニカル"/"セクター構造"/"注目シグナル"
  - "title": 12〜22字の日本語見出し（【】なし、ハッシュタグなし）
  - "body":  上記フォーマット準拠の本文（目安200〜280字、滞在時間を稼ぐ密度）

【ハッシュタグ】
投稿1(index=1)のbody末尾にのみ、空行1つ空けて:
{self.hashtags}
他の投稿にはハッシュタグを付けない。"""

        n_stocks = len(stocks)
        ticker_list_str = "、".join(self._ticker_label(t) for t in stocks.keys())

        user_prompt = f"""今日 {today} の「{self.theme_name}」について、2026年版Xアルゴリズム最適化6投稿スレッドを作成してください。
目的: リプライ誘発(スコア75.0) × 2分以上の滞在時間(最大22倍ブースト) の両取り。

【対象銘柄】{n_stocks}銘柄: {ticker_list_str}
※この{n_stocks}銘柄のみを扱うこと。他の銘柄には言及しない。

【テクニカルデータ（対象{n_stocks}銘柄）】
{stocks_summary}

【関連ニュース（直近）】
{news_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【6投稿の戦略的役割と心理的フック】

1. HOOK（衝撃型フック + 人間味1文） — title例: "{self.theme_name}注目{n_stocks}銘柄、機関の資金が動いた"
   - 冒頭1〜2行で強烈なフック（変化率の衝撃 or 意外性 or "90%が見落とす"系）
   - {n_stocks}銘柄全ての銘柄名と変化率を絵文字+スペース揃えで縦並び
   - "▼ 背景" と "⚠️ 注意点" で因果整理
   - 人間味フレーズを1文混入（"正直このセクターに資金が戻るとは" 等）
   - body末尾に空行1つ空けてハッシュタグ

2. 企業背景（特徴列挙型 / バンドワゴン効果 / 保存誘発） — title例: "急騰の主役{n_stocks}銘柄、事業の本質を解剖"
   - {n_stocks}銘柄それぞれに絵文字見出し + 事業説明2行 + 業界内ポジション1行
   - 銘柄間に必ず空行

3. 一次情報型WHY（EDGAR/公式決算から因果検証） — title例: "EDGAR 10-Qが示す、上昇の真因"
   - "📚 一次情報" セクションで対象{n_stocks}銘柄の公式文書・決算資料から具体的データ引用
   - 二次情報の噂ではなく、一次資料に基づく裏付け
   - {n_stocks}銘柄ごとの一次情報を並置

4. クオンツ・テクニカル（学術根拠型） — title例: "SMA×MACDで見る過熱度、機械学習の示唆"
   - 📊 RSI / 📊 BB%B / 📊 MACD の3データセクション（対象{n_stocks}銘柄のみを並記）
   - 学術的補足（"ランダムフォレスト検証でSMAとMACDの組み合わせが最高精度" 等の事実）
   - ⚠️ 出来高薄商いや異常値を注意喚起

5. セクター構造（フレーミング・逆張り型） — title例: "90%が見落とす、このセクターの本当のリスク"
   - 世間一般の楽観論と異なる構造的リスクをデータで提示
   - ▼ 業界構造 / ▼ 競合動向 / ⚠️ マクロリスク の多層構成
   - 対象{n_stocks}銘柄に関連する構造に絞る

6. 注目シグナル（教えてください型 + リプライ誘発） — title例: "今後の観測ポイント、皆さんはどう見ますか？"
   - ①〜③ で対象{n_stocks}銘柄の具体的観測水準（価格・指標値）を明示（銘柄数に応じて柔軟に）
   - 🔻 反転シグナルを一言
   - 人間味フレーズを1文（"自分が最も注視しているのは③のゾーン" 等）
   - 💬 で議論誘発の問いかけを独立セクションとして末尾に配置
     （{n_stocks}銘柄から「どれが本命」「どれを選ぶ」等の比較形式の問いかけが効果的）

必ずJSON形式のみで回答してください。"""

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=3000,
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
        # Claude出力の body を title と結合して最終的な text を生成する。
        # これにより、プロンプト追従の揺らぎに関わらず常に同じビジュアルになる。
        posts: list[dict] = []
        total = min(len(raw_posts), 6)
        for i, p in enumerate(raw_posts[:6]):
            idx   = int(p.get("index", i + 1))
            role  = p.get("role", "")
            title = p.get("title", "").strip()
            body  = p.get("body", p.get("text", "")).strip()

            # 古いスキーマ互換: body が無く text のみの場合は title を先頭行から抽出
            if not title and body:
                first_line = body.split("\n", 1)[0]
                title = first_line.strip("【】 ").strip()

            # title にハッシュタグが含まれていたら除去（投稿1以外への誤混入を防ぐ）
            title = title.split("#")[0].strip()

            # ─── 2026年Xアルゴリズム最適化: 最終投稿のリプライ誘発を確実化 ───
            # Claudeがプロンプトを無視して問いかけを入れなかった場合のフォールバック。
            # これにより必ずリプライスコア75.0を狙える構造になる。
            if idx == total and idx >= 5:
                body = ensure_discussion_question(body)

            # 投稿1のハッシュタグ確認（body末尾に無ければ追加）
            if idx == 1 and self.hashtags not in body:
                body = body.rstrip() + f"\n\n{self.hashtags}"

            text = format_post_text(idx, title, body)
            posts.append({
                "index": idx,
                "role": role,
                "title": title,
                "text": text,
            })

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
            img_path = image_paths[i] if i < len(image_paths) else None
            media_ids = None
            if img_path and Path(img_path).exists():
                try:
                    media = api_v1.media_upload(filename=img_path)
                    media_ids = [media.media_id_string]
                    print(f"   📸 メディアアップロード完了: post {i+1}")
                except Exception as e:
                    print(f"   ⚠️ メディアアップロード失敗: {e}")
            kwargs: dict = {"text": post["text"]}
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

    def _save_images(self, paths: list[Optional[str]]) -> list[Optional[str]]:
        save_dir = (settings.investment_division_dir
                    / "SNS投稿" / "queue" / date.today().isoformat())
        save_dir.mkdir(parents=True, exist_ok=True)
        saved = []
        for i, p in enumerate(paths):
            if p and Path(p).exists():
                dest = save_dir / f"theme_post{i+1}.png"
                shutil.copy2(p, dest)
                saved.append(str(dest))
            else:
                saved.append(None)
        return saved

    def _save_result(self, today: str, posts: list[dict],
                     thread_url: str, saved: list[Optional[str]]) -> str:
        lines = [
            f"# X投資スレッド（テーマ）— {today} | {self.theme_name}",
            f"**モード**: {'ドライラン' if self.dry_run else '本番投稿'}",
            f"**スレッドURL**: {thread_url}", "",
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
        fname = f"{date.today().isoformat()}_{self.theme_key}_theme_thread.md"
        (save_dir / fname).write_text(result, encoding="utf-8")
        print(f"📄 保存: {save_dir / fname}")
        return result


# ─────────────────────────────────────────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────────────────────────────────────────

def _ph(title: str) -> None:
    print(f"\n{'='*60}\n  {title}\n{'='*60}\n")

def _preview(posts: list[dict]) -> None:
    print("\n📝 生成された台本:\n" + "-" * 55)
    for p in posts:
        print(f"\n【投稿{p.get('index','?')}: {p.get('role','')}】({len(p.get('text',''))}文字)")
        print(p.get("text", ""))
    print("\n" + "-" * 55 + "\n")

def _cleanup(paths: list[Optional[str]]) -> None:
    for p in paths:
        if p:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass
