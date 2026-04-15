# /wiki-to-notebooklm — NotebookLM用エクスポート

`wiki/` の内容をNotebookLMに取り込みやすい形式に変換・出力します。

## 手順

1. `C:/Users/17t14/Documents/Obsidian Vault/wiki/index.md` を読んで全体像を把握
2. 以下のページを収集・読み込み:
   - `wiki/concepts/` 全ファイル
   - `wiki/entities/` 全ファイル
   - `wiki/sources/` 全ファイル
   - `wiki/syntheses/` 全ファイル
3. Obsidianのwikiリンク `[[ページ名]]` を通常テキストに変換（NotebookLM互換）
4. 以下の2ファイルを生成:

### 出力ファイル1: 統合ドキュメント
`C:/Users/17t14/Documents/Obsidian Vault/notebooklm-export/knowledge-base-full.md`

全ページを1ファイルに結合。セクション区切りを `---` で明示。

### 出力ファイル2: サマリーインデックス
`C:/Users/17t14/Documents/Obsidian Vault/notebooklm-export/knowledge-base-index.md`

概念・エンティティ・ソースの一覧と各200字以内の要約。

5. エクスポートログを `wiki/log.md` に追記

## 引数

`/wiki-to-notebooklm` — 全ページをエクスポート  
`/wiki-to-notebooklm concepts` — 概念ページのみ  
`/wiki-to-notebooklm [テーマ名]` — テーマに関連するページのみ

## 出力確認

完了後、以下のファイルをNotebookLMにアップロード:
- `notebooklm-export/knowledge-base-full.md` （メインソース）
- `notebooklm-export/knowledge-base-index.md` （概要ソース）

Google Drive同期設定済みの場合は自動でDriveに反映されます。
