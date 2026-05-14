# ナレッジ連携事業部

**所属**: Arco Capital  
**設立**: 2026-04-12  
**ミッション**: 外部脳（Obsidian Knowledge Base）を構築・維持し、調査・作業・創造の品質を複利で向上させる

---

## 🟡 現在の運用モード (2026-04-21 〜)

| 項目 | 値 |
|------|---|
| **運用モード** | **B (Semi-live)** — 草案生成+オーナー承認後に外部送信 |
| 根拠 | `.octogent/decision.md` (ボードルーム決議) |
| 次回昇格判定 | **2026-04-25 (金)** Phase 1 ゲート判定会議 |
| DM 返信 SLO | **24時間以内** |
| API 日次上限 | **¥1,500** (超過で Kill-switch 自動発火) |
| 指揮系統 | `agents/knowledge/director.py` (KnowledgeDirector) |
| ガードレール | `operations/guardrails.yaml` |

### Phase 1 ゲート通過条件 (4/25 までに)
- Obsidian テンプレパック v1 完成 (3テンプレ以上)
- note LP 公開 (**4/23 厳守**)
- `/wiki-ingest` + `/wiki-lint` の週次運用実績 (7日連続)
- 全社共通: DM-SLO 100% / 監視ダッシュボード稼働 / 炎上0件 / 予算超過0件

---

## 事業部概要

人間とAIの協働における最大のボトルネック「記憶とコンテキストのリセット」を解決する。
調査・学習・作業で得た知識をObsidianに構造化して蓄積し、次のセッションからその知識を活用できるようにする。

---

## Knowledge Base

**Vault path**: `C:/Users/17t14/Documents/Obsidian Vault/`  
**Schema**: Vault内の `CLAUDE.md` を参照

### 4サイクル

| サイクル | コマンド | 内容 |
|---------|---------|------|
| Ingest | `/wiki-ingest` | 新素材を取り込みWikiを更新 |
| Compile | `/wiki-compile` | Wiki全体を再構築・整理 |
| Query | `/wiki-query` | 知識ベースに質問・回答を保存 |
| Lint | `/wiki-lint` | 矛盾・ギャップ・古い情報を検出 |

---

## ディレクトリ構造

```
ナレッジ連携事業部/
├── index.md        # この文書
├── ingest/         # 処理待ちの素材置き場（Vaultのraw/に移す前の一時置き場）
├── projects/       # ナレッジプロジェクト（特定テーマの調査プロジェクト）
└── reports/        # Lintレポート・健康チェック結果
```

---

## 運用フロー

```
1. 記事/論文/メモを発見
        ↓
2. Vaultの raw/ に保存（または ingest/ に一時置き）
        ↓
3. /wiki-ingest を実行
        ↓
4. wiki/ に自動でソース要約・概念ページが生成
        ↓
5. /wiki-query で知識を横断検索
        ↓
6. 定期的に /wiki-lint で品質チェック
```

---

## 担当エージェント

- **Knowledge Curator** (`agents/knowledge/`) — 素材の取り込み・分類・Wiki構築
- **Synthesis Analyst** — 複数ソースの統合分析・洞察の抽出
