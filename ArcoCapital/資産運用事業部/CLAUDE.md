# 資産運用事業部 — Division Schema

## 事業部ミッション

株式投資の専門知識とAI技術を組み合わせ、継続的な利益創出と投資ノウハウの発信を行う。
自動売買システムの運用・改善・分析・SNS発信の4機能を統合的に管理する。

---

## 🟡 現在の運用モード (2026-04-21 〜)

| 項目 | 値 |
|------|---|
| **運用モード** | **B (Semi-live)** — 草案生成+オーナー承認後に外部送信 |
| 根拠 | `.octogent/decision.md` (ボードルーム決議) |
| 次回昇格判定 | **2026-04-25 (金)** Phase 1 ゲート判定会議 |
| DM 返信 SLO | **24時間以内** |
| 実取引モード | **Paper Trading 固定** (RULE-01遵守、実弾は取締役会承認必要) |
| API 日次上限 | **¥1,500** (超過で Kill-switch 自動発火) |
| 指揮系統 | `agents/trading/director.py` (TradingDirector) |
| ガードレール | `operations/guardrails.yaml` |

### Phase 1 ゲート通過条件 (4/25 までに)
- paper trading 週報 草案 1本完成 (モードBで承認経由送信)
- note ¥980 週報販売ページ準備 (手動公開)
- `trade_log.jsonl` 連続7日記録 (RULE-10遵守)
- 全社共通: DM-SLO 100% / 監視ダッシュボード稼働 / 炎上0件 / 予算超過0件

---

## サブ機能一覧

| 機能 | 担当エージェント | 説明 |
|------|----------------|------|
| 自動売買 | InvestmentAnalyst + Trader | 銘柄分析・シグナル生成・注文執行 |
| ハーネスエンジニアリング | StrategyEngineer | 売買手法のバックテスト・改善・プロンプト最適化 |
| 情報収集・SNS発信 | SNSReporter | 投資関連ニュース収集・X(Twitter)投稿生成 |
| 実績共有・SNS発信 | SNSReporter | トレード結果のレポート・X(Twitter)投稿生成 |

---

## ブローカーAPI

| ブローカー | 用途 | SDK |
|-----------|------|-----|
| **Alpaca** | 米国株 自動売買（デフォルト） | `alpaca-py` |
| **MooMoo** | 日本株・米国株 対応予定 | `moomoo-openapi` |

- 環境変数 `BROKER=alpaca` または `BROKER=moomoo` で切り替え
- デフォルト: Alpaca Paper Trading（安全のため）

---

## ディレクトリ構造

```
ArcoCapital/資産運用事業部/
├── CLAUDE.md                  ← 本ファイル（事業部スキーマ）
├── 戦略/                       ← 売買戦略ドキュメント
│   ├── strategy_overview.md   ← 現行戦略の概要
│   └── backtest_results/      ← バックテスト結果保存先
├── 実績/                       ← 取引実績・月次レポート
│   └── [YYYY-MM]/             ← 月別フォルダ（自動生成）
├── SNS投稿/                    ← SNS投稿コンテンツ管理
│   ├── templates/             ← 投稿テンプレート
│   │   ├── trade_result.md    ← 取引結果報告テンプレート
│   │   └── market_news.md     ← マーケット情報テンプレート
│   └── queue/                 ← 投稿待ちコンテンツ（自動生成）
└── レポート/                   ← 分析レポート保存先
```

---

## エージェント構成（agents/trading/）

### InvestmentAnalystAgent
- **役割**: 銘柄の総合分析（テクニカル + ファンダメンタル）
- **入力**: ティッカー、OHLCV、テクニカル指標
- **出力**: BUY/SELL/HOLD シグナル + 根拠レポート

### StrategyEngineerAgent
- **役割**: 自動売買戦略のハーネスエンジニアリング
- **担当**: 過去取引のパターン分析、戦略パラメータ最適化、プロンプト改善提案
- **出力**: 改善提案レポート（`レポート/` に保存）

### SNSReporterAgent
- **役割**: 投資情報・取引実績のSNSコンテンツ生成
- **担当**: X(Twitter)向け投稿文生成（日本語、140字以内）
- **出力**: 投稿テキスト（`SNS投稿/queue/` に保存）

---

## クルー構成（crews/trading/）

### InvestmentCrew
```
InvestmentAnalystAgent → TraderAgent
```
銘柄分析からシグナル生成、注文執行までのフルパイプライン。

### StrategyImprovementCrew
```
StrategyEngineerAgent（単独）
```
過去の取引データを元に売買戦略を評価・改善提案。

### SNSCrew
```
SNSReporterAgent（単独）
```
マーケット情報や取引実績をSNS投稿テキストに変換。

---

## KPI

| 指標 | 目標 |
|------|------|
| 月次リターン | ＋3%以上 |
| 最大ドローダウン | -10%以内 |
| SNS投稿頻度 | 週3回以上 |
| 戦略改善サイクル | 月1回以上 |

---

## 運用フロー

1. **毎日** — `investment_main.py --mode monitor` で価格監視 + アラート
2. **シグナル発生時** — `investment_main.py --mode trade --ticker XXXX` で分析・執行
3. **週次** — `investment_main.py --mode sns --type market_news` でSNS投稿生成
4. **月次** — `investment_main.py --mode strategy-review` で戦略評価・改善

---

## 禁止事項（安全ルール）

- 本番取引は `ALPACA_BASE_URL=https://api.alpaca.markets` を明示的に設定した場合のみ
- デフォルトは必ずペーパートレード
- 1回の注文で資産の10%超を使用しない（リスク管理ルール）
- SNS投稿は具体的な投資アドバイス形式を避ける（金融商品取引法遵守）
