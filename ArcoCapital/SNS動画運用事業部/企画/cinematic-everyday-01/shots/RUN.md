# cinematic-everyday-01 生成 実行手順書 v0.1

**Phase 1 ゲート条件**: 2026-04-22 までに S1/S2/S3 全納品 → 結合 → 公開用アップロード完了
**モード**: **B (Semi-live)** — 公開前にオーナー承認必須
**予算**: 週次 Renoise ¥10,000 上限 (S1 ¥3,500 / S2 ¥3,500 / S3 ¥3,000 = 上限ちょうど)

---

## 0. 事前チェック (5分)

```bash
# 1. L1 検証 (S1-S3 全プロンプトが validator を通過するか)
python -c "
import json
from pathlib import Path
from tools.renoise_validator import validate_prompt_spec
shots_dir = Path('ArcoCapital/SNS動画運用事業部/企画/cinematic-everyday-01/shots')
for p in sorted(shots_dir.glob('S?_prompt.json')):
    validate_prompt_spec(json.loads(p.read_text(encoding='utf-8')))
    print(f'[L1 PASS] {p.name}')
"

# 2. 予算残高確認 (今週の Renoise 消費額)
python -c "
from operations.budget_tracker import BudgetTracker
s = BudgetTracker().snapshot()
print(f'Renoise credits 今週消費: ¥{s[\"renoise_credits\"][\"current\"]:,}')
print(f'Renoise 残高: ¥{s[\"renoise_credits\"][\"weekly_cap\"] - s[\"renoise_credits\"][\"current\"]:,}')
"

# 3. サーキットブレーカ状態確認 (過去10分の失敗が3回未満か)
# → operations/renoise_errors.jsonl の末尾 10 行をチェック
tail -n 10 operations/renoise_errors.jsonl 2>/dev/null || echo "No Renoise errors yet (clean state)."
```

すべて通過したら生成開始。

---

## 1. 生成パスA: Renoise MCP が利用可能な場合

Claude Code 内で Renoise skill が呼び出せる環境なら、L2 ラッパ経由で自動生成できます。

```python
# scripts/run_cinematic_everyday_01.py (未作成、必要時に作る)
import json
from pathlib import Path
from tools.renoise_client import call_renoise_with_guards
from tools.renoise_validator import validate_prompt_spec, validate_output_video, VideoSpec
from operations.budget_tracker import BudgetTracker

tracker = BudgetTracker()
shots_dir = Path("ArcoCapital/SNS動画運用事業部/企画/cinematic-everyday-01/shots")
videos_dir = Path("ArcoCapital/SNS動画運用事業部/企画/cinematic-everyday-01/videos")
videos_dir.mkdir(parents=True, exist_ok=True)

for prompt_path in sorted(shots_dir.glob("S?_prompt.json")):
    prompt = json.loads(prompt_path.read_text(encoding="utf-8"))
    validate_prompt_spec(prompt)  # L1

    weekly_spend = tracker.snapshot()["renoise_credits"]["current"]
    result = call_renoise_with_guards(  # L2
        prompt,
        project_slug="cinematic-everyday-01",
        segment_id=prompt["segment_id"],
        current_weekly_spend_jpy=weekly_spend,
    )

    # L3
    validate_output_video(
        result["video_path"],
        expected=VideoSpec(duration_sec=10.0, width=1080, height=1920),
    )

    tracker.record_usage("renoise_credits", result["cost_jpy"],
                         metadata={"segment": prompt["segment_id"]})
    print(f"[OK] {prompt['segment_id']}: {result['video_path']} (¥{result['cost_jpy']:,})")
```

**注意**: `tools.renoise_client.MockRenoiseInvoker` が現行デフォルト。実 MCP 呼び出しは `RealRenoiseInvoker` を実装して `invoker=...` で渡す (CTO tentacle 4/24 期限)。

---

## 2. 生成パスB: Renoise を手動ブラウザで実行する場合 (MCP 不在時の fallback)

Renoise の web UI を直接開いて手動生成します。各プロンプト JSON を見ながら設定欄に貼り付けてください。

### 2.1 各セグメントの操作手順

```
For each JSON ∈ {S1_prompt.json, S2_prompt.json, S3_prompt.json}:
    1. Renoise web UI を開く
    2. 「New generation」 → 9:16 / 10s / 1080×1920 を選択
    3. Positive prompt 欄に以下を貼る:
         <subject> + ", " + <action>
         Style: <style>
         Camera: <camera>
    4. Negative prompt 欄に以下を貼る:
         <negative>
    5. Generate ボタン (1本あたり ¥3,000〜¥3,500 課金)
    6. 生成完了 (約 60〜90 秒) → Download .mp4
    7. 保存先:
         ArcoCapital/SNS動画運用事業部/企画/cinematic-everyday-01/videos/<Sx>.mp4
    8. L3 検証を走らせる (次項)
```

### 2.2 L3 検証 (各セグメント生成直後)

```bash
python -c "
from pathlib import Path
from tools.renoise_validator import validate_output_video, VideoSpec
for seg in ['S1', 'S2', 'S3']:
    path = Path(f'ArcoCapital/SNS動画運用事業部/企画/cinematic-everyday-01/videos/{seg}.mp4')
    if not path.exists():
        print(f'[SKIP] {seg}: file not yet produced')
        continue
    report = validate_output_video(path, expected=VideoSpec(duration_sec=10.0, width=1080, height=1920))
    print(f'[L3 PASS] {seg}: {report}')
"
```

**失敗ケース**:
- `FaceDetectedError` → セグメント破棄、プロンプト摂動して再生成。**モザイク救済禁止**。
- `OutputSpecError` (尺/解像度) → 再生成
- `ValidatorBackendUnavailableError` → `pip install mediapipe opencv-python` + ffmpeg/ffprobe を PATH に通す

---

## 3. 結合 (全 3 セグ L3 パス後)

```bash
cd "ArcoCapital/SNS動画運用事業部/企画/cinematic-everyday-01/videos"

# concat.txt が未作成なら作成
cat > concat.txt <<'EOF'
file 'S1.mp4'
file 'S2.mp4'
file 'S3.mp4'
EOF

# BGM は後日追加。ここではまず無音で結合。
ffmpeg -f concat -safe 0 -i concat.txt -c copy -movflags +faststart cinematic-everyday-01_silent.mp4

# BGM 追加 + -14 LUFS + フェード (BGM 取得後)
ffmpeg -i cinematic-everyday-01_silent.mp4 \
       -i ../bgm/uppbeat_cinematic_everyday.mp3 \
       -map 0:v -map 1:a -c:v copy -c:a aac \
       -af "volume=-14dB,afade=t=in:ss=0:d=0.5,afade=t=out:st=29.5:d=0.5" \
       -shortest -movflags +faststart \
       cinematic-everyday-01_final.mp4
```

---

## 4. オーナー承認 (Mode B 必須ゲート)

1. `cinematic-everyday-01_final.mp4` を X DM もしくは Discord でオーナーに送信
2. **15 分以内に返信** がなければ公開を保留 (operations/guardrails.yaml の approval_window_sec 900 準拠)
3. 承認が得られたら公開 Step へ、NG なら修正事項をログ化して再生成へ

---

## 5. 公開

```
Instagram Reels / TikTok / YouTube Shorts にクロスポスト
説明文末尾: 「制作代行受付中 / DM で依頼可」
投稿直後に ArcoCapital/SNS動画運用事業部/実績/2026-04/ に案件サマリを記録
```

---

## 6. チェックリスト (Phase 1 ゲート 4/25 提出用)

- [ ] S1/S2/S3 各プロンプト JSON が L1 validator を通過
- [ ] S1/S2/S3 全セグメント生成済 (各 ¥4,000 以下、合計 ¥10,000 以下)
- [ ] S1/S2/S3 全セグメント L3 validator パス (顔検出ゼロ / 尺 10.0±0.5s / 9:16 1080×1920 / 無音)
- [ ] `cinematic-everyday-01_final.mp4` が ffmpeg concat + BGM + -14 LUFS で結合済
- [ ] オーナー承認ログが残っている (X DM / Discord スクショ or メモ)
- [ ] 3プラットフォームにクロスポスト完了
- [ ] `operations/budget_log.jsonl` に 3 セグ分の record_usage が記録されている
- [ ] 本件で `operations/renoise_errors.jsonl` にリトライ上限到達・サーキット発火がない

---

## 7. 失敗時エスカレーション

| 症状 | 対応 |
|------|------|
| L1 で `PromptViolationError` | プロンプト JSON を修正 (subject/action/style から非否定の `face`/`portrait` を除去) |
| L2 で `RenoiseRetryExhaustedError` | 当日 3 回目なら Kill-switch `misfire_detected` 発火 → Mode A 降格 → オーナーへ報告 |
| L2 で `CircuitOpenError` | 15 分待機。解けない場合は Director が運用中断 |
| L2 で `BudgetExhaustedError` | プロジェクトを `status: "blocked"` に書換、来週まで待機 |
| L3 で `FaceDetectedError` | 該当セグメント破棄、プロンプト摂動 (別カメラアングル/別照明) で再生成 |
| L3 で `OutputSpecError` | 尺/解像度/音声を確認、Renoise 設定を修正して再生成 |
