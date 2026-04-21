"""
資産運用事業部 Week1 タスク定義。

Director が以下に委任:
  - InvestmentAnalyst : paper trading の週次テクニカル分析レポート
  - StrategyEngineer  : 過去7日の戦略改善提案
  - SNSReporter       : 週報 note ¥980 の草案 + X/TikTok 短文

RULE-01: paper trading 固定 (BROKER=alpaca-paper / LIVE_TRADING=false)
RULE-10: trade_log.jsonl に全取引判断を記録
"""

from crewai import Agent, Task

from tasks.base_task import make_task


def build_trading_week1_tasks(
    *,
    director: Agent,
    analyst: Agent,
    engineer: Agent,
    reporter: Agent,
    ticker: str = "NVDA",
    api_daily_cap_jpy: int = 1_500,
    weekly_note_price_jpy: int = 980,
) -> list[Task]:

    guardrail_note = (
        f"\n\n## ガードレール (RULE-01/04/10 遵守)\n"
        f"- **Paper Trading 固定**: `BROKER=alpaca-paper` / `LIVE_TRADING=false`\n"
        f"- Anthropic API: **日次 ¥{api_daily_cap_jpy:,} 上限** (超過で Kill-switch)\n"
        f"- trade_log.jsonl: **全判断を記録** (注文・根拠・タイムスタンプ)\n"
        f"- SNS投稿: 金融商品取引法準拠、**具体的投資助言禁止**\n"
        f"- ポジションサイズ: 個別銘柄 **資金の10%以下**\n"
        f"- モード B: 外部送信 (X投稿・note公開) 前に必ずオーナー承認\n"
    )

    analysis_task = make_task(
        description=(
            f"## {ticker} の週次テクニカル分析\n\n"
            "InvestmentAnalyst として以下を実行:\n\n"
            f"1. 直近7日の {ticker} OHLCV データを取得\n"
            "2. テクニカル指標を計算:\n"
            "   - RSI(14), SMA(20), MACD\n"
            "3. BUY/SELL/HOLD シグナルを生成 (判断曖昧なら HOLD)\n"
            "4. ストップロス -5% / 利確目標 +10% を計算\n"
            "5. ポジションサイズは総資産の 10% 以下に制限\n"
            "6. `logs/trade_log.jsonl` に分析結果を追記\n"
            + guardrail_note
        ),
        expected_output=(
            f"## 銘柄分析: ${ticker}\n"
            "- シグナル: BUY / SELL / HOLD\n"
            "- テクニカル根拠 (RSI / SMA / MACD の具体値)\n"
            "- 推奨エントリー・ストップロス・利確目標\n"
            "- ポジションサイズ (%)\n"
            "- trade_log.jsonl 追記行"
        ),
        agent=analyst,
        output_file=f"trading/week1_analysis_{ticker}.md",
    )

    strategy_task = make_task(
        description=(
            "## 過去7日の戦略改善提案\n\n"
            "StrategyEngineer として以下を実行:\n\n"
            "1. `logs/trade_log.jsonl` の直近7日分をレビュー\n"
            "2. 勝率・平均利益・平均損失・プロフィットファクターを算出\n"
            "3. 問題パターン (連敗シグナル / 根拠の薄い判断) を抽出\n"
            "4. 改善提案 3 点 (パラメータ調整案を数値で)\n"
            "5. 次週の戦略パラメータを提案\n"
            + guardrail_note
        ),
        expected_output=(
            "## 戦略改善レポート\n"
            "- 週次パフォーマンス指標 (勝率・PF・損益)\n"
            "- 問題パターン 3 点\n"
            "- 改善提案 3 点 (具体数値付き)\n"
            "- 次週パラメータ案"
        ),
        agent=engineer,
        output_file="trading/week1_strategy.md",
    )
    strategy_task.context = [analysis_task]

    report_task = make_task(
        description=(
            f"## paper trading 週報 note 草案 (¥{weekly_note_price_jpy})\n\n"
            "SNSReporter として以下を実行:\n\n"
            "1. 分析 + 戦略改善レポートを素材に、note 週報 (¥980) を草案\n"
            "   - 長さ: 2000-3000字\n"
            "   - 構成: 市場サマリ / 保有銘柄 / 売買判断 / 学び / 来週の見通し\n"
            "2. X (日本語140字以内) の速報投稿を 3 本草案\n"
            "3. TikTok 縦型動画の台本を 1 本草案 (60秒以内)\n"
            "4. **具体的投資助言は禁止**、「〜という視点もある」「〜の可能性」等の情報提供表現に限定\n"
            "5. note 販売ページの有料/無料境界を明示\n"
            + guardrail_note
        ),
        expected_output=(
            f"## 週報パッケージ (¥{weekly_note_price_jpy} 想定)\n"
            "- note 本文草案 (2000-3000字、有料/無料境界マーカー付き)\n"
            "- X 投稿 3 本 (140字以内)\n"
            "- TikTok 台本 1 本 (60秒以内)\n"
            "- オーナー承認チェックリスト (金融商品取引法チェック含む)"
        ),
        agent=reporter,
        output_file="trading/week1_report.md",
    )
    report_task.context = [analysis_task, strategy_task]

    director_task = make_task(
        description=(
            "## Week1 総括 + オーナー承認依頼\n\n"
            "TradingDirector として以下を統合すること:\n\n"
            "1. 3タスク (分析・戦略・週報) の成果物サマリ\n"
            "2. Phase 1 ゲート (4/25) の 3条件:\n"
            "   - PAPER_WEEKLY: paper trading 週報 草案 1本完成\n"
            "   - NOTE_LP_TRADING: note ¥980 販売ページ準備 (手動公開)\n"
            "   - TRADE_LOG_7D: trade_log.jsonl 連続7日記録\n"
            "3. RULE-01/04/10 遵守状況のセルフチェック\n"
            "4. 外部送信待ち項目 (X投稿・note公開) の一覧\n"
            + guardrail_note
        ),
        expected_output=(
            "## Week1 総括レポート\n"
            "- 3タスク成果物リンク\n"
            "- Phase 1 ゲート達成率\n"
            "- RULE遵守セルフチェック結果\n"
            "- オーナー承認待ちアイテム\n"
            "- 経営陣へのエスカレーション事項"
        ),
        agent=director,
        output_file="trading/week1_director_summary.md",
    )
    director_task.context = [analysis_task, strategy_task, report_task]

    return [analysis_task, strategy_task, report_task, director_task]
