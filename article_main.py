"""
article_main.py — XArticleCrew 実行用 CLI エントリポイント

【重要な運用ルール】
このクルーは X Articles（記事機能）専用です。
通常のロングツイート投稿は行いません。
`--publish` を付けると MD を保存したうえで Chrome の Article Composer
（x.com/compose/articles）に貼り付けるためのガイドを表示します。
実際の Publish ボタンはユーザーがブラウザで押してください。

使用例:
    # ドライラン（生成のみ、Composer ガイドも表示しない）
    python article_main.py \\
        --title "イラン戦争が株式相場にもたらしたもの" \\
        --context "中東情勢の激化、原油/防衛/安全資産への影響、エネルギー株の変動を定量分析"

    # 本番: MD 保存 + X Article Composer 用貼り付けテキスト生成
    python article_main.py \\
        --title "小休止を得たAI関連株の未来" \\
        --context "2025年後半のハイプサイクル減速、収益化局面への移行、設備投資減速リスク" \\
        --length medium \\
        --horizon 12months \\
        --publish

    # 短めで長期視点
    python article_main.py \\
        --title "ロボ・宇宙テーマが呼ぶ鉱物資源銘柄の展望" \\
        --length short \\
        --horizon 24months \\
        --tickers MP,LYSDY,ALB,LIT,REMX,URA
"""

import argparse
import sys

from dotenv import load_dotenv
load_dotenv(override=True)  # .env が空のシステム環境変数より優先されるように

from crews.trading.x_article_crew import XArticleCrew


def main():
    parser = argparse.ArgumentParser(
        description="XArticleCrew — 長期マクロテーマ型 X Articles（記事機能）生成",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--title", required=True,
                        help="アーティクルのタイトル（必須）")
    parser.add_argument("--context", default="",
                        help="テーマの要点・焦点（自由記述、Claudeへのヒント）")
    parser.add_argument("--tickers", default="",
                        help="明示指定銘柄カンマ区切り（例: MP,ALB,LIT）")
    parser.add_argument("--length", choices=["short", "medium", "long"],
                        default="medium",
                        help="目標長: short(2000-2500字) / medium(2500-3500字) / long(3500-5000字)")
    parser.add_argument("--horizon", choices=["6months", "12months", "24months"],
                        default="12months",
                        help="分析の時間軸（既定: 12months）")
    parser.add_argument("--publish", action="store_true",
                        help="X Article Composer 向けの貼り付けガイドを出力する"
                             "（既定はドライラン = 生成のみ）")
    parser.add_argument("--chart-set", default="auto",
                        help=(
                            "チャート構成の選択: "
                            "auto(LLMが自動選定/既定) | "
                            "default/geopolitics/sector/risk/macro/flow/commodity/tech_cycle "
                            "(プリセット) | "
                            "'key1,key2,key3,key4' (4つのチャート名を直接指定)"
                        ))

    args = parser.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()] if args.tickers else []

    crew = XArticleCrew(
        title=args.title,
        context=args.context,
        tickers=tickers,
        target_length=args.length,
        time_horizon=args.horizon,
        dry_run=not args.publish,
        chart_set=args.chart_set,
    )
    crew.run()


if __name__ == "__main__":
    sys.exit(main())
