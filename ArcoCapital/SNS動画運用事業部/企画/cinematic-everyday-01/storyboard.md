# cinematic-everyday-01 — 絵コンテ (Storyboard) v0.1

**Project slug**: `cinematic-everyday-01`
**Title**: Cinematic Everyday — 日常が映画になる瞬間
**Platform**: Instagram Reels (9:16) / TikTok / YouTube Shorts
**Total**: 3 segments × 10秒 = 30秒 尺
**Mode**: **B (Semi-live)** — 公開前にオーナー承認
**完成期限**: 2026-04-22 (Phase 1 ゲート条件)

---

## 企画意図

- 「日常の0.5秒」を35mmフィルム質感で切り取り、**手・シルエット・物のみ** で情感を成立させる
- 制作代行の営業素材 → 飲食・美容・治療院・士業 の小規模事業者に「御社の日常もこうなる」と訴求
- 顔出しゼロのため、プライバシー検出リスクを L3 結果検証で遮断
- BGM は無音 (ポートフォリオ規格)、公開時に著作権フリー音源を合成

---

## スタイル仕様 (3セグ共通)

| 項目 | 値 |
|------|---|
| アスペクト比 | 9:16 |
| 解像度 | 1080×1920 |
| 尺 | 各 10.0 秒 (±0.5s 許容) |
| ルック | Cinematic realism / 35mm film look / shallow depth of field / film grain |
| カラーグレード | 暖色寄り (morning 2700K / noon 5500K / evening 3000K) |
| カメラ動作 | ハンドヘルド微振動 (overshoot なし) |
| 音声 | 無音で納品 (結合後に BGM 合成) |

---

## セグメント S1 — Morning / 目覚め

**時間帯**: 06:30 / **尺**: 10.0s / **主色**: 淡いブルー＋電球色 (2700K)

| t | 映像 | カメラ | 音 |
|---:|------|------|----|
| 0.0–2.5s | カーテンの端に指先が触れる、レースがふわっと揺れる | 手元マクロ f/1.4 | 無音 |
| 2.5–5.0s | 指がカーテンを横に引く、外から朝日が差す (逆光) | 低角度、光源に向かって | 無音 |
| 5.0–7.5s | シルエットが光の中に浮かぶ (胸から下のみ) | Wide、被写界深度浅 | 無音 |
| 7.5–10.0s | 手のひらが光を受ける、finger tips に hair light | 手マクロ、光に向かって | 無音 |

**Renoise prompt skeleton**:
```
subject: woman's hand (hands only, no face, no portrait),
  fingertips touching sheer curtain, backlit by morning sunlight
action: curtain slowly parted by hand, light spilling in
style: cinematic realism, 35mm film, shallow depth of field (f/1.4),
  film grain, warm sunrise palette (2700K accents on cool blue)
camera: handheld slight jitter, low angle looking up toward light
duration: 10s / aspect: 9:16 / no audio
negative: face, portrait, person's face, people visible from chest up,
  watermark, text overlay
```

**L1/L3 セルフチェック**:
- [ ] `negative` に `face` / `portrait` が含まれている
- [ ] 尺 10.0s ±0.5s
- [ ] 顔検出 0 件 (mediapipe)
- [ ] 音声トラックなし

---

## セグメント S2 — Noon / 静寂

**時間帯**: 12:40 / **尺**: 10.0s / **主色**: ニュートラル (5500K) + 木材

| t | 映像 | カメラ | 音 |
|---:|------|------|----|
| 0.0–3.0s | 木製テーブル、片手がコーヒーカップを包む、湯気マクロ | オーバーヘッド斜め、f/2 | 無音 |
| 3.0–6.0s | 反対の手でハードカバー本を開く、ページがパラパラ | 45° 上から、本に焦点 | 無音 |
| 6.0–8.5s | 窓の外の街並みが hard light でボケ | 手前にシルエット (胸下) | 無音 |
| 8.5–10.0s | 指がページにそっと触れて止まる | 指先マクロ | 無音 |

**Renoise prompt skeleton**:
```
subject: woman's hands only (no face visible),
  one hand cradling a ceramic coffee cup with rising steam,
  other hand opening a hardcover book on wooden table
action: steam rising, book page turning slowly, hand settling on page
style: cinematic realism, 35mm film, shallow depth of field (f/2),
  film grain, neutral daylight (5500K) with warm wood tones
camera: 45° overhead angle, static with micro handheld jitter
duration: 10s / aspect: 9:16 / no audio
negative: face, portrait, person from chest up, watermark, text overlay
```

**L1/L3 セルフチェック**:
- [ ] `negative` に `face` / `portrait` が含まれている
- [ ] 尺 10.0s ±0.5s
- [ ] 顔検出 0 件
- [ ] 音声トラックなし

---

## セグメント S3 — Evening / 帰路

**時間帯**: 18:20 / **尺**: 10.0s / **主色**: 暖色 (3000K) + 青紫の空

| t | 映像 | カメラ | 音 |
|---:|------|------|----|
| 0.0–2.5s | 夕空の下、マンション玄関前。手のシルエットが鍵を握る | Low angle、空に向かって | 無音 |
| 2.5–5.0s | 鍵を差し込む、鍵穴のマクロ | 鍵穴マクロ、f/1.8 | 無音 |
| 5.0–7.5s | ドアがゆっくり開き、室内の電球色が漏れる | 鍵穴側から内側へ | 無音 |
| 7.5–10.0s | 手が扉を押さえる、足元だけが室内に踏み込む | 低角度、扉のシルエット | 無音 |

**Renoise prompt skeleton**:
```
subject: woman's hand only (no face, no upper body above waist),
  hand holding a metal house key in front of apartment door,
  key entering lock cylinder
action: key inserted slowly, door opening inward, warm interior light
  spilling out against cool evening sky
style: cinematic realism, 35mm film, shallow depth of field (f/1.8),
  film grain, evening palette (3000K warm interior + blue-purple sky)
camera: low angle, then macro on keyhole, then interior push-in
duration: 10s / aspect: 9:16 / no audio
negative: face, portrait, person's face, watermark, text overlay,
  logos on door, readable text on signage
```

**L1/L3 セルフチェック**:
- [ ] `negative` に `face` / `portrait` が含まれている
- [ ] 尺 10.0s ±0.5s
- [ ] 顔検出 0 件
- [ ] 音声トラックなし

---

## 結合仕様 (ffmpeg)

```
ffmpeg -f concat -safe 0 -i videos/concat.txt \
       -i bgm/uppbeat_cinematic_everyday.mp3 \
       -map 0:v -map 1:a -c:v copy -c:a aac \
       -af "volume=-14dB,afade=t=in:ss=0:d=0.5,afade=t=out:st=29.5:d=0.5" \
       -shortest -movflags +faststart \
       videos/cinematic-everyday-01_final.mp4
```

- `concat.txt` は既存 (`videos/concat.txt`)
- BGM 音量は **-14 LUFS** 相当 (Instagram Reels 推奨値)
- フェードイン/アウト各 0.5 秒

---

## 納品フロー (Mode B)

```
1. S1/S2/S3 を Renoise で並列生成 (30s cap / 各 ¥4k 上限)
       ↓ 各セグ L3 検証パス
2. ffmpeg で結合 + BGM 合成 + -14 LUFS 調整
       ↓
3. 生成物を outputs/sns_video/cinematic-everyday-01_final.mp4 に保存
       ↓
4. オーナーに X DM で「承認依頼」通知 (Mode B 必須ゲート)
       ↓ 承認
5. Instagram Reels / TikTok / YouTube Shorts にクロスポスト
   投稿本文末尾: 「制作代行受付中 / DM で依頼可」
       ↓
6. ArcoCapital/SNS動画運用事業部/実績/2026-04/ に案件サマリを記録
```

---

## 予算計画

| 項目 | 想定 |
|------|-----:|
| S1 生成 | ¥3,500 |
| S2 生成 | ¥3,500 |
| S3 生成 | ¥3,000 |
| **合計** | **¥10,000** (週次 Renoise 上限ちょうど) |

**注意**: S1/S2 で ¥7,000 消費時点で Renoise 予算 70% 到達 → Amber 警告。S3 開始前に BudgetTracker.snapshot() で残高確認必須。

---

## 関連ファイル

- `project.json` — ショット管理 JSON (v0.2 で `mode: "B"` へ修正済)
- `videos/concat.txt` — ffmpeg 結合用ファイルリスト
- `ArcoCapital/経営陣/Renoise例外処理設計書.md` — L1/L2/L3 防御壁 (本絵コンテと同時 PR 化)

---

## 変更履歴

| 版 | 日付 | 変更者 | 内容 |
|---|------|--------|------|
| v0.1 | 2026-04-21 | SNSVideoDirector tentacle + Main Claude | 初版 — 3セグ × 10s、プロンプト雛形、L3 チェックリスト、-14 LUFS |
