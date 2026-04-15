"""
銘柄分析タスク — InvestmentAnalystAgent 用

make_analysis_task()     — 指定銘柄の総合テクニカル分析
make_trade_decision_task() — 分析結果をもとに注文判断を下すタスク
"""

from crewai import Task

from tasks.base_task import make_task


def make_analysis_task(ticker: str, agent) -> Task:
    """
    指定銘柄のテクニカル分析タスク。

    Args:
        ticker: 銘柄ティッカーシンボル（例: "AAPL"）
        agent:  InvestmentAnalystAgent.build() で生成したエージェント
    """
    return make_task(
        description=f"""
{ticker} の株式を総合的に分析し、明確な売買シグナルを生成してください。

【分析手順】
1. 直近30日のOHLCVデータを取得する
2. 以下のテクニカル指標を計算・評価する:
   - RSI(14): 30以下=過売り(BUYチャンス)、70以上=過買い(SELLチャンス)
   - SMA(20): 現在価格との位置関係・傾きでトレンド判定
   - MACD: シグナルラインとのクロスでモメンタム判定
3. 各指標を総合してシグナル（BUY/SELL/HOLD）を決定する
4. エントリー価格・ストップロス(-5%)・利確目標(+10%)を計算する
5. ポジションサイズ推奨（総資産の何%か）を算出する

【重要】
- 判断が難しい場合は必ずHOLDを選択する
- ストップロスは必ず設定すること
- 根拠のない直感的な判断は行わない
""",
        expected_output=f"""
以下のフォーマットで{ticker}の分析結果を日本語で報告する:

## 銘柄分析: ${ticker}

### シグナル: BUY / SELL / HOLD （いずれか1つ）

### テクニカル根拠
- RSI(14): [数値] → [判定コメント]
- SMA(20): [数値] → [トレンド方向]
- MACD: [ヒストグラム値] → [判定コメント]
- 現在価格: $[数値]

### 総合評価
[200字以内の総合コメント]

### 推奨アクション
- アクション: BUY / SELL / HOLD
- 推奨エントリー価格: $[数値]
- ストップロス: $[数値] ([%])
- 利確目標: $[数値] ([%])
- 推奨ポジションサイズ: 総資産の[%]
""",
        agent=agent,
        output_file=f"analysis_{ticker}.md",
    )


def make_trade_decision_task(ticker: str, analysis_result: str, agent) -> Task:
    """
    分析結果をもとに最終的な注文決定を行うタスク。

    Args:
        ticker:          銘柄ティッカー
        analysis_result: make_analysis_task の出力テキスト
        agent:           TraderAgent.build() で生成したエージェント
    """
    return make_task(
        description=f"""
以下のアナリスト分析に基づいて、{ticker} の注文を実行してください。

【分析結果】
{analysis_result}

【実行ルール】
- シグナルが BUY の場合: 推奨サイズで成行または指値注文を発注する
- シグナルが SELL の場合: 保有ポジションがあれば決済注文を発注する
- シグナルが HOLD の場合: 注文は行わず、理由を報告する
- ペーパートレード環境（ALPACA_BASE_URL に "paper" を含む）では必ずペーパー注文

【安全ルール】
- 1銘柄のポジションは総資産の10%を超えてはならない
- ストップロス注文を必ずセットで発注する
""",
        expected_output=f"""
注文実行結果を日本語で報告する:

## 注文実行レポート: ${ticker}

### 実行アクション: BUY / SELL / HOLD

### 注文詳細（BUY/SELLの場合）
- 注文種別: 成行 / 指値
- 数量: [株数]
- 注文価格: $[数値]
- ストップロス設定: $[数値]
- 注文ID: [ID または "ペーパー注文"]

### スキップ理由（HOLDの場合）
[スキップの理由]

### 備考
[その他特記事項]
""",
        agent=agent,
    )
