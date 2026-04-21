# KPI通達 補足 — モードB即日稼働指示

**宛先**: TradingDirector (agents/trading/director.py)
**発信元**: CEO (Arco Capital 取締役会)
**日付**: 2026-04-21 (JST)
**根拠**: `.octogent/decision.md` (2026-04-21 ボードルーム最終決議)
**対象**: 2026-04-18 発行の「KPI通達_2026-04-18.md」の執行モード確定

---

## 🟡 本日より運用モード **B (Semi-live)** で稼働開始

### 変更点
- 月次 KPI (¥10,000 / paper trading 週報 note販売) は **据え置き**
- 執行モードは **モード C は否決、モード B 即日稼働**
- 4/25 ゲート通過条件 (下記) をクリアした場合のみ Mode C 段階移行
- **実取引は永続的に Paper Trading 固定** (RULE-01遵守、実弾化は別途取締役会承認必須)

---

## 🎯 Week 1 (4/21〜4/25) 最優先 5 タスク

| # | タスク | DoD (完了判定) | 期限 |
|---|--------|---------------|:---:|
| 1 | paper trading 週報 草案 1本完成 (note ¥980 想定) | `SNS投稿/queue/` に草案、オーナー承認後公開 | **4/25** |
| 2 | note ¥980 週報販売ページ準備 (LP + 有料部分分離) | 販売ページURL記録 (手動公開可) | **4/25** |
| 3 | `trade_log.jsonl` 連続7日記録 (RULE-10遵守) | `logs/trade_log.jsonl` に 7日分のエントリ | **4/25** |
| 4 | StrategyEngineer による戦略改善レポート 1本 | `ArcoCapital/資産運用事業部/レポート/` に保存 | **4/25** |
| 5 | X/TikTok への paper trading 進捗投稿 (モードB承認経由) | 週3本以上、承認滞留15分以内 | 毎日 |

---

## 🚨 安全ルール (RULE-01〜10 遵守)

- **RULE-01**: 実取引禁止。`BROKER=alpaca-paper` 固定、`LIVE_TRADING=false` 環境変数必須
- **RULE-04**: サイレントフォールバック禁止。例外は必ず stderr + `incident_log.jsonl` へ
- **RULE-10**: 全取引判断を `logs/trade_log.jsonl` に記録 (注文内容・判断根拠・タイムスタンプ)
- **ポジションサイズ**: 個別銘柄 **資金の10%以下** (paper trading でも同規律)

---

## 🚨 ハードキャップ (超過で Kill-switch 自動発火)

| 項目 | 上限 | 警告閾値 |
|------|-----:|--------:|
| Anthropic API (日次) | **¥1,500** | ¥1,200 (80%) |

---

## 📋 報告義務

- **毎朝 09:00 (JST)**: 前日の取引判断サマリを `logs/trade_log.jsonl` で記録
- **金曜 17:00**: Week1 サマリ + 週報草案を取締役会に提出
- **誤投稿検知**: 即 `python -m operations.kill_switch --trigger misfire_detected`

---

**署名**: Arco Capital CEO
**参照**: `.octogent/decision.md` / `ArcoCapital/経営陣/運用モード.md` / `AGENTS.md`
