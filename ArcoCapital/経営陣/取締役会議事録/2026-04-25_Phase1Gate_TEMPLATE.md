# 2026-04-25 Phase 1 ゲート判定会議 (TEMPLATE)

> **※ このファイルはテンプレートです。当日、実データで埋めて保存し直してください。**
> 保存時のファイル名: `2026-04-25_Phase1Gate.md` (`_TEMPLATE` を外す)

---

## 会議情報

| 項目 | 値 |
|------|----|
| 開催日時 | 2026-04-25 (金) XX:XX JST |
| 議長 | CEO |
| 書記 | Main Claude (Moderator) |
| 議題 | Phase 1 ゲート通過判定 — Mode B 継続 / Phase 2 (Mode C 昇格) / 延期 / 撤退 |
| 所要時間 | 60 分 (想定) |
| 根拠ドキュメント | `.octogent/decision.md` (Boardroom 4/18 決議) / `operations/guardrails.yaml` |

## 出席役員

- [ ] 🦸 CEO (manager_agent)
- [ ] 💰 CFO
- [ ] 💻 CTO
- [ ] 🏃 COO
- [ ] 📣 CMO
- [ ] 🎨 CPO
- [ ] 🎙️ Moderator (Main Claude)

---

## 1. 共通 4 条件の検証 (全事業部共通)

| # | 条件 | 実測 (4/25 時点) | 判定 | 根拠ソース |
|--:|------|---------------|:---:|----------|
| 1 | DM 応答 SLO 100% (24h 以内) | XX% (計測対象: XX 件) | ⬜ Pass / ⬜ Fail | `operations/dm_log.csv` + ダッシュボード |
| 2 | 監視ダッシュボード稼働 (日次自動) | 4/21〜4/25 全日 Green or Amber | ⬜ Pass / ⬜ Fail | `ArcoCapital/経営陣/監視レポート/YYYY-MM-DD.md` |
| 3 | 炎上・誤投稿 0 件 | XX 件 | ⬜ Pass / ⬜ Fail | `operations/incident_log.jsonl` |
| 4 | 予算超過 0 件 (Red 発生 0) | XX 件 | ⬜ Pass / ⬜ Fail | `operations/budget_log.jsonl` + `budget_status.json` |

### 共通 4 条件サマリ
- Pass: X / 4
- Fail: X / 4
- → **全 4 通過なら次節 (事業部別) へ。1件でも Fail なら撤退 or 延期を即時議論。**

---

## 2. 事業部別条件

### 2.1 ナレッジ連携事業部 (note 編集部)

| 条件 | 実測 | 判定 | 根拠 |
|------|------|:---:|------|
| Week 1 author LP 公開済 (¥2,980 note 有料記事) | 4/23 公開 XX:XX | ⬜ Pass / ⬜ Fail | note URL |
| LP 売上 / 閲覧 | X 本 / XX view | (参考値) | note ダッシュボード |
| 読者コメント / 質問 | XX 件 | (参考値) | 同上 |

**Director コメント (書き手)**:
> (自由記述)

### 2.2 Instagram 運用事業部

| 条件 | 実測 | 判定 | 根拠 |
|------|------|:---:|------|
| 日次リール投稿継続 (4/20〜4/25 = 6日) | XX / 6 日 | ⬜ Pass / ⬜ Fail | Instagram 運用履歴 |
| 漫画事業部キャラ3人継承 | ⬜ Yes / ⬜ No | ⬜ Pass / ⬜ Fail | 投稿内容目視 |
| フォロワー数 (4/25 時点) | XX 人 | (参考値 — 1万目標への進捗) | Instagram Insights |

**Director コメント**:
> (自由記述)

### 2.3 SNS 動画運用事業部

| 条件 | 実測 | 判定 | 根拠 |
|------|------|:---:|------|
| `cinematic-everyday-01` 3セグ全納品・結合・公開 | S1/S2/S3 = ⬜/⬜/⬜ 公開 = ⬜ | ⬜ Pass / ⬜ Fail | `企画/cinematic-everyday-01/videos/cinematic-everyday-01_final.mp4` + 3プラットフォーム URL |
| Renoise 例外処理設計書 PR 化 + 実装 (`tools/renoise_client.py` / `renoise_validator.py`) | PR 番号 #XX | ⬜ Pass / ⬜ Fail | GitHub PR |
| 制作代行 LP 公開 (note or HP、手動可) | 公開 URL | ⬜ Pass / ⬜ Fail | note / HP URL |

**Director コメント**:
> (自由記述)

---

## 3. 役員発言 (各 200〜300 字)

### 💰 CFO (収益性・保守的)
> (本日までの予算消費、月次 ¥100k 目標への進捗、Mode C 昇格がキャッシュフローに与える影響)

### 💻 CTO (技術負債・懐疑的)
> (Renoise 3層防御の実装状況、`tools/` の未カバーテスト、サイレントフォールバックが発生していないか)

### 🏃 COO (実行可能性・現場視点)
> (各事業部 Director の稼働状況、SLO 違反事案、次週のボトルネック)

### 📣 CMO (集客戦略)
> (LP 2本の流入導線、Instagram フォロワー獲得速度、Mode C 昇格時の露出計画)

### 🎨 CPO (商品定義)
> (¥2,980 LP の売上推移、制作代行の受注可能性、次商品の構想)

### 🦸 CEO (ビジョナリー)
> (上記をすべて踏まえた最終判断を次節へ)

---

## 4. 最終判定

### 投票 (各役員 GO / HOLD / NO-GO)

| 役員 | 投票 | 確信度 (-1.0〜+1.0) |
|------|:---:|:-------------------:|
| CEO | ⬜ GO / ⬜ HOLD / ⬜ NO-GO | +0.X |
| CFO | ⬜ GO / ⬜ HOLD / ⬜ NO-GO | +0.X |
| CTO | ⬜ GO / ⬜ HOLD / ⬜ NO-GO | +0.X |
| COO | ⬜ GO / ⬜ HOLD / ⬜ NO-GO | +0.X |
| CMO | ⬜ GO / ⬜ HOLD / ⬜ NO-GO | +0.X |
| CPO | ⬜ GO / ⬜ HOLD / ⬜ NO-GO | +0.X |

**判定ルール** (Boardroom 判定閾値と同じ):
- 平均 +0.4 以上 → **GO** (Phase 2 = Mode C 昇格)
- 平均 -0.4 以下 → **NO-GO** (撤退 or 事業再編)
- それ以外 → **HOLD** (Mode B 継続 + 追加条件提示)

### 集計
- 平均スコア: +0.XX
- 票分布: GO=X / HOLD=X / NO-GO=X
- **総合判定**: ⬜ GO / ⬜ HOLD / ⬜ NO-GO

---

## 5. 決議事項

### 5.1 総合判定に基づくアクション
- GO の場合:
  - 4/26 以降 `operations/guardrails.yaml` の `active_mode` を **C (Full-live)** に書換 (CEO 指示で実行)
  - 各事業部は外部送信・投稿の **オーナー承認プロセスを自動化** (人間承認省略可、記録は継続)
- HOLD の場合:
  - Mode B を 1 週間延長 (次回判定: 2026-05-02)
  - 不足条件を具体化して Director へ指示
- NO-GO の場合:
  - 不合格事業部を **Mode A (Dry-run)** に降格
  - 撤退基準の見直しを翌週までに CFO+COO が提出

### 5.2 撤退基準の確認 (1 ヶ月 = 5/18 期限)
- 月次 ¥100,000 売上達成なら Phase 2 継続
- ¥50,000 未達成なら事業縮小再設計
- ¥20,000 未達成なら全事業撤退検討

---

## 6. 次回までの宿題

| 担当 | タスク | 期日 |
|------|-------|-----|
| CTO | (判定次第で差し替え) |  |
| COO | 週次レビュー更新 | 5/2 |
| CMO | (判定次第で差し替え) |  |
| CPO | (判定次第で差し替え) |  |

---

## 7. 備考 / オフレコ

> (メモ・雑談・未記録にしたい事項)

---

_本議事録は Arco Capital 取締役会 4/18 決議に基づき、Phase 1 ゲート判定を記録するものです。
議事録の保存率 100% は経営陣 KPI (`ArcoCapital/経営陣/CLAUDE.md`) の必達条件です。_
