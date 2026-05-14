# KPI通達 補足 — モードB即日稼働指示

**宛先**: SNSVideoDirector (agents/sns_video/director.py)
**発信元**: CEO (Arco Capital 取締役会)
**日付**: 2026-04-21 (JST)
**根拠**: `.octogent/decision.md` (2026-04-21 ボードルーム最終決議)
**対象**: 2026-04-18 発行の「KPI通達_2026-04-18.md」の執行モード確定

---

## 🟡 本日より運用モード **B (Semi-live)** で稼働開始

### 変更点
- 月次 KPI (¥100,000 / 制作代行6本 + テンプレ5本) は **据え置き**
- 執行モードは **モード C は否決、モード B 即日稼働**
- 4/25 ゲート通過条件 (下記) をクリアした場合のみ Mode C 段階移行

### モード B の行動原則
1. **草案は全て生成OK** — X投稿文、LP文案、見積書、DM返信草案
2. **外部送信の前に必ずオーナー承認** — 承認キュー滞留上限 **15分**
3. **有料クレジット消費は OK** (Renoise 週次 ¥10,000 上限内)
4. 誤操作検知時は即 `operations/kill_switch.py --trigger misfire_detected`

---

## 🎯 Week 1 (4/21〜4/25) 最優先 5 タスク

| # | タスク | DoD (完了判定) | 期限 |
|---|--------|---------------|:---:|
| 1 | `cinematic-everyday-01` 3セグ生成 + 結合 + BGM + アップロード | 公開URLが `ArcoCapital/SNS動画運用事業部/実績/` に記録 | **4/25** |
| 2 | Renoise 例外処理・リトライ境界・回路遮断の **設計書 PR 化** (CTO と連携) | PR が `main` に merge | **4/25** |
| 3 | 制作代行 LP 公開 (note or 独自HP) | 公開URL記録 + 初回DM1件獲得 | **4/25** |
| 4 | DM受信→初回返信 **24h 以内** の運用実績積み上げ | X DM ログで 100% 達成 | **4/25** |
| 5 | 日次コスト報告 (Renoise + API) を `operations/budget_log.jsonl` で毎朝確認 | Amber(70%) 到達時に CFO 通知 | 毎日 |

---

## 🚨 ハードキャップ (超過で Kill-switch 自動発火)

| 項目 | 上限 | 警告閾値 |
|------|-----:|--------:|
| Renoise クレジット (週次) | **¥10,000** | ¥7,000 (70%) |
| Anthropic API (日次) | **¥1,500** | ¥1,200 (80%) |

超過時の挙動は `ArcoCapital/経営陣/Kill-Switch設計書.md` を参照。
**オーナー判断の事前許可なしに上限を上書きすることは禁止 (RULE-04)**。

---

## 📋 報告義務

- **毎朝 09:00 (JST)**: 前日の進捗サマリを `operations/budget_log.jsonl` + `ArcoCapital/SNS動画運用事業部/実績/YYYY-MM/daily_YYYY-MM-DD.md` に記録
- **金曜 17:00**: Week1 サマリを取締役会に提出 (Phase 1 ゲート判定会議の入力)
- **Red 指標発生時**: 即 Kill-switch or COO へ報告 (遅延厳禁)

---

## 🤝 他事業部との連携

- **CTO / ナレッジ連携事業部**: Renoise 例外処理設計書のレビュー
- **資産運用事業部**: Week1 配信素材のシェア (投資テーマ動画は paper trading 週報と並走可)

---

**署名**: Arco Capital CEO
**参照**: `.octogent/decision.md` / `ArcoCapital/経営陣/運用モード.md` / `ArcoCapital/経営陣/Phase1_ゲート判定_2026-04-25.md`
