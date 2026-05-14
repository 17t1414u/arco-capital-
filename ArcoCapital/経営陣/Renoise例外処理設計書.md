# Renoise 例外処理・リトライ境界・回路遮断 設計書 v0.1

> **根拠**: `.octogent/decision.md` § 4 合意条件 — CTO 拘束条件 #2
> **担当**: CTO (設計) / SNSVideoDirector (運用)
> **ステータス**: v0.1 (Phase 0 暫定・4/25 ゲート前に PR 化必須)
> **対象モジュール**: `agents/sns_video/video_generator.py` + 将来実装される `tools/renoise_client.py`

---

## 1. 背景と目的

SNS動画運用事業部は **Renoise(renoise:director / renoise:renoise-gen)** を本編生成の主ツールとして採用している。2026-04-05 以降の実測で以下の失敗モードが確認されている:

| 失敗モード | 発生例 | 現状の挙動 |
|-----------|--------|-----------|
| **生成タイムアウト** | 9:16 セグメント生成が 120s 超で応答なし | 無限待機 → プロセス詰まり |
| **非決定的失敗** | 同一プロンプトで 3回中 1回失敗 | サイレントに ¥を消費するだけ |
| **クレジット異常消費** | 1 セグメントで想定の 3倍を消費 | 週次上限 ¥10,000 を突破し Kill-switch 発火 |
| **顔検出フィルタ発火** | "hands only" 指定でも人物顔を誤生成 → フィルタで rejected | 再試行で再消費する無限ループ |

本設計書は RULE-04 (サイレントフォールバック禁止) に則り、**「壊れたら止める/記録する/オーナーに見える形で通知する」** を達成する最小設計を定める。

---

## 2. 3層の防御壁

```
  [Renoise 呼び出し]
        │
        ▼
  ┌─ L1: 構文前置チェック ───────────────┐
  │  プロンプト仕様違反を呼び出し前に弾く       │
  │  (顔指定禁止ルール/尺範囲/解像度 等)      │
  └──────────────────────────────────────┘
        │ pass
        ▼
  ┌─ L2: 実行境界ガード ─────────────────┐
  │  タイムアウト / リトライ上限 / 予算残高   │
  │  すべてハードキャップで実行を包む         │
  └──────────────────────────────────────┘
        │ pass
        ▼
  ┌─ L3: 結果検証 ──────────────────────┐
  │  返却動画の顔検出・尺・解像度・音声を     │
  │  ダウンストリーム公開前に必ず確認         │
  └──────────────────────────────────────┘
        │ pass
        ▼
  納品フロー (ffmpeg 結合 → オーナー承認 → 公開)
```

各層で検知した失敗は **無視せず** `operations/renoise_errors.jsonl` に構造化記録し、必要に応じて Kill-switch にエスカレーション。

---

## 3. 各層の仕様

### 3.1 L1: 構文前置チェック

呼び出し前に `validate_prompt_spec(prompt: dict) -> None` で以下を検査:

| チェック項目 | 違反時の挙動 |
|-------------|------------|
| `subject` に `face` / `portrait` / `closeup_face` 等の禁止語が含まれていないか | `PromptViolationError` を送出・呼び出し中止 |
| `duration_sec` が 1 ≤ x ≤ 30 の範囲か | 同上 |
| `aspect_ratio` が `9:16` / `1:1` / `16:9` のいずれか | 同上 |
| `negative_prompt` に著作権侵害語が含まれていないか | 同上 |

**RULE-04 準拠**: 違反時は例外送出のみ。自動補正しない (勝手にフォールバックせずオーナーに判断させる)。

### 3.2 L2: 実行境界ガード

実行ラッパ `call_renoise_with_guards(...)` が以下の境界を強制:

| 境界 | 値 (v0.1) | 超過時の挙動 |
|-----|---------:|-------------|
| **タイムアウト** | 120 秒/セグメント | `RenoiseTimeoutError` 送出 → L2リトライ起動 |
| **リトライ上限** | 2 回 (合計 3 試行) | 3 回目失敗で `RenoiseRetryExhaustedError`、Director を当該プロジェクト Mode A 降格 |
| **セグメント単価上限** | ¥4,000/セグメント | 超過したら即停止、該当 project.json を `status: "blocked"` に書換 |
| **週次予算残高** | ¥10,000 — `BudgetTracker.snapshot()` の `renoise_credits` から逆算 | 残高 < セグメント単価上限なら起動前に停止 |
| **回路遮断 (circuit breaker)** | 直近 10 分で 3 回連続失敗 → 15 分間 全生成を停止 | `CircuitOpenError` 送出、INCIDENT 記録 |

リトライ戦略: **指数バックオフ** (2s → 4s → 8s)、かつ **同一プロンプトの再投入は禁止** (プロンプト摂動が必要)。同一プロンプト連投は Renoise 側のレートリミット違反に繋がる実測あり。

### 3.3 L3: 結果検証

Renoise から返却された `.mp4` に対し、公開パイプライン投入前に以下を確認:

| 検査 | 手段 | NG 時 |
|-----|------|-------|
| **顔検出** | `opencv-haar` or `mediapipe` で顔ランドマーク検出 | 1件でも検出されたら `FaceDetectedError`、該当セグメント破棄・再生成キュー投入 |
| **尺** | `ffprobe -show_entries format=duration` | 仕様 ±0.5s を超えたらリジェクト |
| **解像度** | `ffprobe -show_streams` | 仕様と不一致なら破棄 |
| **音声トラック** | `ffprobe -select_streams a` | 音声ありならミュート化 (ポートフォリオ規格で無音) |

**禁止**: 顔検出時に自動モザイクで救済すること (ブランド毀損 + 二次的なプライバシーリスク)。発見したら捨てる。

---

## 4. データ構造

### 4.1 `operations/renoise_errors.jsonl`

全失敗を構造化記録。BudgetTracker と同じ JSON Lines フォーマット。

```json
{"ts": "2026-04-22T10:14:22+09:00", "layer": "L2", "error": "RenoiseTimeoutError",
 "project_slug": "cinematic-everyday-01", "segment": "S1", "attempt": 2,
 "elapsed_sec": 121.3, "prompt_hash": "a3b5c7…", "cost_jpy_so_far": 3200}
```

### 4.2 `RenoiseError` 例外階層

```python
class RenoiseError(RuntimeError): ...
class PromptViolationError(RenoiseError):  pass  # L1
class RenoiseTimeoutError(RenoiseError):   pass  # L2
class RenoiseRetryExhaustedError(RenoiseError): pass  # L2
class CircuitOpenError(RenoiseError):      pass  # L2
class FaceDetectedError(RenoiseError):     pass  # L3
```

呼び出し元は **`RenoiseError` を広く捕捉しない**。必ず個別 except で対応 (RULE-04)。
唯一例外: Director 層の最上位 except で `RenoiseError` を捕捉し `renoise_errors.jsonl` への記録と kill_switch 判定を実施。

---

## 5. Kill-switch との連動

| イベント | Kill-switch 連動 |
|---------|------------------|
| `RenoiseRetryExhaustedError` が 同一日内 3 回発生 | `misfire_detected` トリガ発火 → 全事業部 Mode A 降格 |
| `CircuitOpenError` が 24h 以内 2 回発生 | `misfire_detected` トリガ発火 |
| 週次 Renoise 予算の 90% 到達 | `budget_breach` トリガ発火 (BudgetTracker 既実装) |
| `FaceDetectedError` が1件でも発生 | **オーナー通知のみ** (Kill-switch 非連動)、incident_log へ記録 |

---

## 6. 実装ロードマップ

| 段階 | 作業 | 担当 | 期限 |
|-----|------|------|-----:|
| **設計書 (本 PR)** | 本文書を `ArcoCapital/経営陣/` に配置 | CTO | 2026-04-21 |
| `operations/renoise_errors.jsonl` 形式確定 | スキーマ合意 | CTO | 4/21 |
| `tools/renoise_client.py` (L2 ラッパ) | タイムアウト + リトライ + サーキットブレーカ | SNSVideoDirector | 4/23 |
| `tools/renoise_validator.py` (L1+L3) | 構文前置 + ffprobe 結果検証 | SNSVideoDirector | 4/24 |
| `agents/sns_video/video_generator.py` 差し替え | 既存モック → 本実装 | SNSVideoDirector | 4/24 |
| Smoke Test (`cinematic-everyday-01` S1で走らせる) | Director 経由で 1セグ生成 | SNSVideoDirector | 4/24 |
| Phase 1 ゲート提出 | 上記 5件を PR マージ済で提出 | CTO | **4/25** |

---

## 7. 非ゴール (v0.1 では扱わない)

- Renoise 以外のプロバイダ (Veo / Pika) へのフォールバック — **明示的に禁止** (RULE-04 サイレントフォールバック防止)
- 顔検出の自動モザイク救済 — § 3.3 の通り禁止
- 生成結果のキャッシング/再利用 — v0.2 以降で検討

---

## 8. PR チェックリスト

- [ ] `RenoiseError` 階層が単体テストでカバーされている
- [ ] L1 違反プロンプト・L2 タイムアウト・L3 顔検出 の3シナリオで例外が送出される
- [ ] `renoise_errors.jsonl` に JSON Lines 形式で記録される
- [ ] `budget_tracker.record_usage("renoise_credits", …)` が実行境界内で呼ばれる
- [ ] Circuit breaker の発火/復帰が time-dependent テストでカバーされている
- [ ] 同一プロンプト連投がガードされている (摂動必須)
- [ ] kill_switch.py のトリガに `misfire_detected` が接続されている
- [ ] PR 本文に 「週次 Renoise 予算残高が所定値を下回ったら起動前に停止」の挙動を明記

---

## 9. 変更履歴

| 版 | 日付 | 変更者 | 内容 |
|---|------|--------|------|
| v0.1 | 2026-04-21 | CTO tentacle + Main Claude | 初版 — 3層防御・例外階層・Kill-switch連動・PRチェックリスト |
