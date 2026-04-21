# Kill-Switch 設計書 v0.1 — Emergency Stop & Rollback Runbook

> **作成者**: CTO tentacle (ボードルーム拘束条件)
> **根拠**: `.octogent/decision.md` § 4 合意条件 —「ロールバック手順とKill-switch明文化」(CTO 譲れない一線)
> **実装**: `operations/kill_switch.py`
> **ステータス**: v0.1 (Phase 0 暫定版、4/25 ゲート前に v0.2 レビュー)

---

## 1. Kill-Switch とは

Arco Capital の自動運用系統を **3秒以内に全停止** し、全事業部を Mode A (Dry-run) に差し戻すための単一エントリポイント。
RULE-04 (サイレントフォールバック禁止) に従い、発火は必ずログに記録され、オーナーに通知される。

---

## 2. 発火トリガー (4種)

| ID | トリガー | 発火源 | 自動/手動 |
|----|----------|--------|:--------:|
| T1 | `budget_breach` | `BudgetTracker.record_usage()` が閾値超過を検知 | 自動 |
| T2 | `flaming_incident_reported` | オーナーが X DM / GitHub issue で「炎上」報告 | 手動 |
| T3 | `misfire_detected` | CI / 監視ダッシュボードが誤投稿を検知 | 自動 |
| T4 | `manual` | オーナー判断 | 手動 |

---

## 3. 発火コマンド

### 手動 (推奨パス)
```bash
python -m operations.kill_switch --trigger manual --reason "深夜の炎上対応、全停止"
```

### プログラマティック (Python)
```python
from operations.kill_switch import fire
fire("budget_breach", reason="anthropic_api daily limit reached", bucket="anthropic_api")
```

### 自動発火 (BudgetTracker 内蔵)
```python
from operations.budget_tracker import BudgetTracker, BudgetBreach
from operations.guardrails_loader import load_guardrails

tracker = BudgetTracker(guardrails=load_guardrails())
try:
    tracker.record_usage("anthropic_api", jpy=1600, source="sns_video_director")
except BudgetBreach as exc:
    # Kill-switch を明示的に発火させる (サイレント継続は禁止)
    from operations.kill_switch import fire
    fire("budget_breach", reason=str(exc), bucket=exc.bucket)
    raise
```

---

## 4. 発火時のアクション (自動)

1. **事業部モード差し戻し**
   `operations/guardrails.yaml` の `divisions.*.mode` と `active_mode` を全て **A** に書き換え
2. **インシデント記録**
   `operations/incident_log.jsonl` に発火時刻・トリガー・理由を追記
3. **stderr 通知**
   `[KILL-SWITCH FIRED]` メッセージと手順ガイドへのリンクを出力
4. **終了コード**
   呼び出しプロセスは終了コード `2` で異常終了

### 4.1 将来 (v0.2) で追加する通知経路
- X DM への push (X API 経由、Director アカウント側で受信)
- 標準メール通知 (Gmail API 経由)
- Obsidian Vault の `_alerts/` フォルダに Markdown 追記 (外部脳と連携)

---

## 5. 発火後のオーナー対応フロー

```
Kill-Switch 発火
      │
      ▼
┌──────────────────────────────────────────┐
│ 1. operations/incident_log.jsonl の最新行を確認  │
│    (trigger / reason / downgraded_divisions)    │
└──────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────┐
│ 2. トリガー別のリカバリ手順に従う (§6 参照)    │
└──────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────┐
│ 3. 原因除去後、手動で guardrails.yaml の          │
│    active_mode / divisions[].mode を B に戻す     │
│    (自動復旧はしない = CTO 拘束条件)            │
└──────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────┐
│ 4. 3事業部長エージェントに「復旧通知」を送付      │
│    (Trading/SNSVideo/Knowledge Director)        │
└──────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────┐
│ 5. 次回取締役会議事録に事後分析 (RCA) を追記     │
└──────────────────────────────────────────┘
```

**重要**: 自動復旧は実装しない。オーナーが原因を確認し、明示的に Mode A → B へ昇格させる。

---

## 6. トリガー別リカバリ手順

### T1: budget_breach (予算超過)
1. `operations/budget_status.json` で超過 bucket を特定
2. 超過理由を分析 (暴走ループ / 意図的集中作業 / 単純超過)
3. 翌日/翌週まで Mode A 据え置き **OR** 上限引き上げを取締役会で提案
4. CFO が承認したら `guardrails.yaml` の該当 `*_limit_jpy` を改定

### T2: flaming_incident_reported (炎上)
1. 対象投稿 URL と一次苦情を `.octogent/incidents/` に保存
2. オーナー本人が **DM 返信・削除判断・謝罪投稿** (オーナー専権)
3. COO 拘束条件「初動30分」の達成可否を記録
4. 累計炎上件数が 2 件に達したら **Mode B 恒久化** (CFO 拘束条件)

### T3: misfire_detected (誤投稿)
1. 誤投稿の内容と Director 判断ログを `.octogent/incidents/` に保存
2. 該当 Director のプロンプトを見直し、回帰テストを追加
3. 該当事業部のみ Mode A → B へ **手動昇格** (他事業部は影響させない)

### T4: manual (オーナー手動)
1. `--reason` に記録された理由に応じて対応
2. 単なる訓練・テストなら `incident_log.jsonl` にその旨を追記してから復旧

---

## 7. Kill-switch 非採用の理由 (設計判断の記録)

| 採用しなかった案 | 理由 |
|----------------|------|
| `kill -9` プロセス強制終了 | ログが残らない / RULE-04 違反 |
| ファイル削除で無効化 | 復旧手順が属人化する |
| Mode A ではなく全停止 | 草案生成は継続したいユースケースあり (LLM学習目的) |
| Slack 通知 | 本プロジェクトは Slack 未導入。Phase 2 以降で検討 |

---

## 8. テスト手順 (Phase 0)

```bash
# 1. Dry run (guardrails.yaml を書き換えない検証モードは将来追加)
python -m operations.kill_switch --trigger manual --reason "smoke test"

# 2. incident_log.jsonl の最終行を確認
tail -n 1 operations/incident_log.jsonl

# 3. guardrails.yaml の active_mode が A に変わっていることを確認
grep "^active_mode:" operations/guardrails.yaml

# 4. 手動で B に復旧
#    (sed や Edit tool で active_mode: B に書き戻し、divisions[].mode: B も同様)
```

---

## 9. 未解決課題 (v0.2 で対応)

- [ ] X API の自動 DM 通知実装
- [ ] Gmail API 経由のメール通知
- [ ] `--dry-run` フラグの追加 (guardrails.yaml を書き換えずに振る舞いだけ確認)
- [ ] ロールバック用の `guardrails.yaml` スナップショット履歴保存
- [ ] Director エージェントのランタイム停止フック (現状は次回呼び出し時まで停止反映されない)

---

## 10. 変更履歴

| 版 | 日付 | 変更者 | 内容 |
|---|------|--------|------|
| v0.1 | 2026-04-21 | CTO tentacle + Main Claude | 初版 — 4トリガー / guardrails.yaml 書換 / incident_log 追記 |
