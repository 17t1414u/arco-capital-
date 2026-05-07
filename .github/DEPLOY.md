# 🚀 GitHub Actions クラウド移行デプロイ手順

このドキュメントはローカル Windows タスクから GitHub Actions への移行手順です。
所要時間: **30〜45分**（Push権限の解決状況による）

---

## 📋 事前確認

| 項目 | 状態 |
|---|---|
| ローカル Windows 4タスク | **✅ Disabled 済み**（クラウド完成まで取引停止中）|
| `.github/workflows/*.yml` | ✅ 作成済み（朝バッチ + 日中スキャン） |
| Linux 互換性 | ✅ Python コードに Windows パスのハードコードなし |
| `requirements.txt` | ✅ 全依存ライブラリ網羅済み |

---

## 🔑 STEP 1: GitHub Push 権限の解決

過去に `git push` が 403 エラー（`17t1414u/arco-capital-` への write 権限なし）。
以下のいずれかで解決:

### 方法A: Personal Access Token (PAT) 使用
1. https://github.com/settings/tokens にアクセス
2. **Generate new token (classic)** をクリック
3. Scopes: `repo` (full control of private repositories) を選択
4. 生成された token をコピー
5. ローカルで以下を実行:
   ```bash
   cd C:/Users/17t14/Desktop/Claude
   git remote set-url origin https://<TOKEN>@github.com/17t1414u/arco-capital-.git
   git push origin main
   ```

### 方法B: SSH キー使用
1. SSH キー生成: `ssh-keygen -t ed25519 -C "17t1414u@gmail.com"`
2. `~/.ssh/id_ed25519.pub` の内容をコピー
3. https://github.com/settings/keys に追加
4. ローカルで:
   ```bash
   git remote set-url origin git@github.com:17t1414u/arco-capital-.git
   git push origin main
   ```

### 方法C: GitHub CLI 認証
```bash
gh auth login        # ブラウザ認証
gh auth status       # 確認
git push origin main
```

---

## 🔐 STEP 2: GitHub Secrets の登録

リポジトリ設定で必要な環境変数を Secrets として登録します。

1. https://github.com/17t1414u/arco-capital-/settings/secrets/actions
2. **New repository secret** で以下を順次登録:

| Secret 名 | 値の例 | 必須 |
|---|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-api03-xxx...` | ✅ |
| `MODEL_NAME` | `anthropic/claude-sonnet-4-5` | ✅ |
| `ALPACA_API_KEY` | `PK2RGICL...` | ✅ |
| `ALPACA_SECRET_KEY` | `xxx...` | ✅ |
| `ALPACA_BASE_URL` | `https://paper-api.alpaca.markets` | ✅ |
| `ALPACA_DATA_URL` | `https://data.alpaca.markets` | ✅ |

ローカルの `.env` ファイルから値をコピペすると確実です:
```bash
grep -E "^(ANTHROPIC|ALPACA|MODEL_NAME)" C:/Users/17t14/Desktop/Claude/.env
```

⚠️ **トークン値は 1度しか確認できないので、登録時に確実にコピーすること。**

---

## 🌐 STEP 3: Alpaca IP allowlist の解除

GitHub Actions runner は実行ごとに動的IPが割り当てられるため、固定IP制限を外す必要があります。

1. https://app.alpaca.markets/paper/dashboard/overview にログイン
2. 左メニュー → **Account** → **API Keys**
3. 該当キー（`PK2RGICL...`）の編集
4. **IP Restrictions** を以下のいずれかに変更:
   - **オプション A（推奨）**: IP制限を**完全に解除**（GitHub Actionsの全レンジを許可）
   - **オプション B**: GitHub Actions の IP レンジを追加（メンテナンス煩雑、非推奨）
5. 保存

⚠️ **本番口座ではなく Paper Trading 口座のみであること**を確認してください。

---

## 📦 STEP 4: コードを Push

```bash
cd C:/Users/17t14/Desktop/Claude
git add .github/ trading/ crews/ agents/ scripts/ config/ \
        investment_main.py main.py test_connection.py trading_main.py \
        ArcoCapital/資産運用事業部/CLAUDE.md
git status                       # 変更内容を確認
git commit -m "feat: GitHub Actions対応 + strategy v2.3 + Path C SHORT 対応"
git push origin main
```

---

## ✅ STEP 5: 手動実行で動作確認

クラウド側で workflow が正しく動くかを **手動 trigger** で検証します。

1. https://github.com/17t1414u/arco-capital-/actions にアクセス
2. 左メニュー: `Trading Morning Batch (Auto Pipeline)` を選択
3. 右上: **Run workflow** → ブランチ `main` で実行
4. 実行ログで以下を確認:
   - ✅ `pip install` 成功
   - ✅ `check_market_timing.py` の出力
   - ✅ `investment_main.py --mode auto --live` 開始
   - ⚠️ 市場 CLOSED 時間帯なら `[SKIP]` で正常終了
5. 完了後、**Artifacts** から `morning-batch-logs-xxxx` をダウンロード → ログ内容確認

### 期待する出力（市場 CLOSED 中の手動実行例）

```
[SKIP] market opens in 433.0 min — outside 1-45min window
```

または市場 OPEN 時の場合:

```
[GO] market opens in 7.5 min ...
🤖 全自動モード起動
📦 STEP 0/5: 既存ポジション評価＆エグジット判断...
...
```

---

## 🔁 STEP 6: 自動実行の確認（最初の平日朝バッチ）

cron は UTC ベースで設定済み:

| Workflow | UTC | JST | 米国時刻 |
|---|---|---|---|
| Morning Batch (EDT) | 13:20 | 22:20 | 9:20 EDT |
| Morning Batch (EST) | 14:20 | 23:20 | 9:20 EST |
| Intraday Scan (EDT) | 17:00 | 02:00翌 | 13:00 EDT |
| Intraday Scan (EST) | 18:00 | 03:00翌 | 13:00 EST |

両時刻が登録されているので、夏時間 / 冬時間関係なく自動的に1日1回（市場OPEN10分前）動きます。
両方発火しても `check_market_timing.py` で適切な方のみ通過します。

---

## ⚠️ STEP 7: ローカル Windows タスクの永久停止

クラウド実行が安定稼働を確認したら、ローカルタスクを完全削除:

```powershell
schtasks /delete /tn "ArcoCapital_Trading_EDT" /f
schtasks /delete /tn "ArcoCapital_Trading_EST" /f
schtasks /delete /tn "ArcoCapital_Intraday_EDT" /f
schtasks /delete /tn "ArcoCapital_Intraday_EST" /f
```

---

## 🆘 トラブルシューティング

### Q1. workflow が起動しない
→ GitHub Actions の使用量制限（パブリックは無制限、プライベートは月2000分）を確認

### Q2. Alpaca 403 エラー
→ Step 3 の IP allowlist 解除が反映されているか再確認

### Q3. `ModuleNotFoundError`
→ `requirements.txt` に必要なライブラリが入っているか確認

### Q4. Anthropic 認証エラー
→ Secrets の `ANTHROPIC_API_KEY` の値が正しいか確認

### Q5. 同日重複ガードが効かない
→ クラウド実行では runner が毎回 fresh なので、`outputs/daily-state/*.json` は引き継がれない。代わりに**concurrency group** で同時実行を防ぐ（既に workflow YAML で設定済み）

---

## 📊 移行完了後の運用

- **ログの確認**: GitHub Actions の `Actions` タブ → 各 run の Artifacts ダウンロード
- **ポジション確認**: https://app.alpaca.markets/paper/dashboard/overview
- **コスト**: GitHub Actions 無料枠で十分（朝バッチ 60min/日 × 22日 = 1,320 分/月 < 2,000分制限）
- **API コスト**: 別途 Anthropic ($45-90/月) + Alpaca (paper無料)

---

## ✨ 次のステップ（任意）

- Slack/Discord 通知連携（バッチ完了時に summary 通知）
- 失敗時の自動リトライ
- Notion DB に取引履歴を記録
