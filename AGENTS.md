# AGENTS.md — ハーネスエンジニアリング 全エージェント共通ルール

> **Always On** — このファイルはすべてのエージェントセッションで常時適用される。
> Agent = Model + Harness の原則に基づき、LLMの確率的挙動を決定論的制御層で包む。

---

## 1. 絶対的安全制約（Safety Constraints）— 違反禁止

```
RULE-01: 外部APIへの書き込み操作は、明示的な LIVE_TRADING=true かつ
         人間の承認（Human-in-the-Loop）がない限り実行しない。
RULE-02: デフォルトはすべてペーパートレード（ALPACA_BASE_URL に "paper" を含む）。
RULE-03: 1銘柄のポジションサイズは総資産の10%を超えてはならない。
RULE-04: サイレントなフォールバックは禁止。エラーは必ずログに記録して例外を発生させる。
RULE-05: ファイルサイズは300行以内。超過する場合はモジュール分割する。
RULE-06: 不可逆的なコマンド（rm, DROP TABLE, 強制送金等）はツールスキーマから排除する。
RULE-07: 外部APIコールはすべてリードオンリーとする（書き込みは明示的に許可された場合のみ）。
RULE-08: 戦略の自動デプロイは Hold-out バックテストで現行戦略を上回った場合のみ。
RULE-09: デプロイ後48時間以内にシャープレシオが基準値を下回った場合は自動ロールバック。
RULE-10: すべての取引決定はtrade_log.jsonlに構造化ログとして記録する。
```

---

## 2. エージェント組織構造（TradingAgents フレームワーク）

```
【アナリストチーム】（並列実行 — 情報収集）
  FundamentalsAnalyst  → 財務諸表・企業価値分析
  SentimentAnalyst     → SNS・市場センチメント数値化
  NewsAnalyst          → ニュース・マクロ経済分析
  TechnicalAnalyst     → テクニカル指標・チャートパターン

【リサーチャーチーム】（弁証法的推論 — 意見の対立と統合）
  BullResearcher       → 強気シナリオの論拠構築
  BearResearcher       → 弱気シナリオの論拠構築

【意思決定層】
  RiskManager          → ポートフォリオリスク評価・承認ゲート
  FundManager          → 最終取引判断（Buy/Sell/Hold + サイズ）

【自己改善層】（オプティマイザループ — 週次/月次）
  Optimizer            → パフォーマンス分析・strategy.md 更新提案
```

---

## 3. エージェント行動規約

### 3.1 出力規約
- **結論先出し（BLUF形式）**: 結論を最初に、根拠を後から
- **数値根拠必須**: 「良さそう」「悪そう」などの感覚的表現は禁止
- **日本語出力**: すべての分析・報告を日本語で行う（ティッカーは英語）
- **不確実時はHOLD**: 判断が難しい場合は必ずHOLDを選択する

### 3.2 ツール使用規約
- テクニカル指標の計算は `trading/tools/indicators.py` の既存関数を使用
- 価格データ取得は `trading/tools/alpaca_tools.py` 経由のみ
- 直接的なHTTPリクエストやos.system()の呼び出しは禁止
- ファイル書き込みは `trading/harness/trade_log.py` 経由のみ

### 3.3 委任規約
- アナリストチーム: `allow_delegation = False`（専門領域に集中）
- FundManager: `allow_delegation = True`（リスクマネージャーに承認要求可）
- Optimizer: `allow_delegation = False`（提案のみ、実行は人間が判断）

---

## 4. ハーネス制御パターン

| パターン | 方向 | 実装場所 | 内容 |
|---------|------|---------|------|
| Capability-limiting | フィードフォワード | alpaca_tools.py | 不可逆コマンドをスキーマから排除 |
| Approval Gate | フィードバック | full_trading_crew.py | 執行前にRiskManagerの承認を必須化 |
| State Machine | 制御基盤 | trade_log.py | 取引状態の追跡・無限ループ検知 |
| Circuit Breaker | フィードバック | guardrails.py | 同一エラー3回連続でシステム停止 |
| Structural Tests | フィードバック | guardrails.py | ポジションサイズ・ドローダウン違反検知 |

---

## 5. ログ仕様（trade_log.jsonl）

すべての取引決定は以下の構造でログに記録する:

```json
{
  "timestamp": "2026-04-15T10:30:00",
  "ticker": "AAPL",
  "action": "BUY",
  "entry_price": 195.50,
  "position_size_pct": 0.05,
  "signals": {
    "fundamentals": "BULLISH",
    "sentiment": "NEUTRAL",
    "news": "BULLISH",
    "technical": "BUY"
  },
  "bull_thesis": "...",
  "bear_thesis": "...",
  "risk_approved": true,
  "outcome": null,
  "quality_score": null
}
```

`outcome` と `quality_score`（1〜5）はポジションクローズ後に更新する。

---

## 6. strategy.md 管理規約

- `trading/harness/strategy.md` が現行の売買戦略の **唯一の真実の情報源**
- Optimizerは提案のみ行い、人間の承認後に `strategy_v{N}.md` として保存
- 旧バージョンは `trading/harness/strategy_history/` にアーカイブ
- strategy.md の変更はバックテスト検証なしに本番適用しない

---

## 7. 自己改善ループのスケジュール

```
タスクループ    : 毎回の取引セッション（on-demand）
               → アナリスト → リサーチ → リスク → 執行

オプティマイザループ : 週次/月次（手動 or スケジュール）
               → 過去ログ分析 → パターン抽出 → strategy.md 改訂案生成
               → バックテスト検証 → 人間の承認 → デプロイ
```

---

## 8. 禁止事項

- `strategy.md` の内容に反する取引の実行
- ロールバック機能をバイパスしての強制デプロイ
- リスクマネージャーの承認なしでの本番注文
- ログなしでの取引実行
- 品質スコアのない状態での戦略最適化の実行
