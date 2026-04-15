"""
戦略評価タスク — StrategyEngineerAgent 用（ハーネスエンジニアリング）

make_strategy_review_task() — 過去取引データの分析・戦略改善提案
make_backtest_design_task() — バックテストシナリオ設計タスク
"""

from crewai import Task

from tasks.base_task import make_task


def make_strategy_review_task(trade_history: str, period: str, agent) -> Task:
    """
    過去の取引履歴を分析し、戦略改善提案を生成するタスク。

    Args:
        trade_history: 取引履歴（JSON文字列または整形済みテキスト）
        period:        評価期間（例: "2026年3月", "直近30日"）
        agent:         StrategyEngineerAgent.build() で生成したエージェント
    """
    return make_task(
        description=f"""
以下の取引履歴（{period}）を分析し、現行の自動売買戦略を評価・改善してください。

【取引履歴】
{trade_history}

【現行戦略パラメータ】
- RSI閾値: BUY=35以下、SELL=70以上
- ストップロス: -5%
- 利確目標: +10%
- 使用指標: RSI(14), SMA(20), MACD(12/26/9)

【ハーネスエンジニアリング分析手順】
1. **パフォーマンス集計**: 勝率・平均利益・平均損失・プロフィットファクターを算出
2. **失敗パターン抽出**: 損失トレードの共通点を特定（指標の誤シグナル等）
3. **パラメータ感度分析**: RSI閾値・ストップロスの変更が結果に与える影響を推定
4. **プロンプト改善点**: AIエージェントへの指示文で改善できる箇所を特定
5. **改善提案の優先度付け**: 期待改善効果の大きい順に並べる

【重要】
- 「なんとなく良さそう」という提案は行わない
- すべての提案に数値的根拠を添える
- 保守的な改善から開始する（大幅な変更よりも小さな調整を優先）
""",
        expected_output=f"""
以下のフォーマットで戦略評価レポートを日本語で作成する:

## 戦略評価レポート: {period}

### パフォーマンス概要
- 総取引数: [N]回
- 勝率: [%]
- 平均利益: +[%]
- 平均損失: -[%]
- プロフィットファクター: [値]
- 最大ドローダウン: -[%]

### 問題パターン（失敗トレード分析）
1. [パターン名]: [頻度]回 — [原因]
2. [パターン名]: [頻度]回 — [原因]

### 改善提案（優先度順）
#### 1位: [改善項目]
- 現状: [現パラメータ/プロンプト]
- 提案: [変更内容]
- 期待効果: [改善予測]
- 根拠: [データ・ロジック]

#### 2位: [改善項目]
（同上形式）

### 次バージョン（v[X.X]）パラメータ案
- RSI BUY閾値: [旧値] → [新値]
- RSI SELL閾値: [旧値] → [新値]
- ストップロス: [旧値] → [新値]
- 利確目標: [旧値] → [新値]

### 実装優先度
- 即時適用推奨: [項目]
- 次回バックテスト後に適用: [項目]
- 要継続観察: [項目]
""",
        agent=agent,
        output_file=f"strategy_review_{period.replace(' ', '_')}.md",
    )


def make_backtest_design_task(strategy_params: dict, agent) -> Task:
    """
    新しい戦略パラメータのバックテストシナリオを設計するタスク。

    Args:
        strategy_params: テストするパラメータ辞書
        agent:           StrategyEngineerAgent.build() で生成したエージェント
    """
    params_text = "\n".join(f"- {k}: {v}" for k, v in strategy_params.items())

    return make_task(
        description=f"""
以下のパラメータ変更案に対してバックテストシナリオを設計してください。

【テスト対象パラメータ】
{params_text}

【設計内容】
1. テスト期間の選定（最低3ヶ月、理想は1年）
2. テスト対象銘柄の選定（現ウォッチリスト vs 拡張リスト）
3. 評価指標の定義（何をもって「改善」とするか）
4. パラメータグリッドサーチの設計（試す組み合わせ一覧）
5. 合否判定基準の設定
""",
        expected_output="""
バックテストシナリオ設計書を日本語で作成する:

## バックテストシナリオ設計書

### テスト設定
- 期間: [開始日] 〜 [終了日]
- 対象銘柄: [リスト]
- 初期資本: $[金額]

### パラメータグリッド
[テストするパラメータの組み合わせ表]

### 評価基準（合否判定）
- 最低勝率: [%]以上
- 最低プロフィットファクター: [値]以上
- 最大ドローダウン: -[%]以内

### 実行コマンド（擬似コード）
```python
# バックテスト実行例
for rsi_buy in [30, 35, 40]:
    for stop_loss in [0.03, 0.05, 0.07]:
        result = backtest(rsi_buy=rsi_buy, stop_loss=stop_loss)
        evaluate(result)
```

### 期待成果
[このバックテストで何を検証・証明したいか]
""",
        agent=agent,
        output_file="backtest_design.md",
    )
