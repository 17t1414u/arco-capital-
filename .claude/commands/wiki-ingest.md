# /wiki-ingest — 新素材の取り込み

Obsidian Vault の `raw/` にある未処理ファイルをWikiに取り込みます。

## 手順

1. `C:/Users/17t14/Documents/Obsidian Vault/CLAUDE.md` を読んでVaultのスキーマを確認する
2. `C:/Users/17t14/Documents/Obsidian Vault/raw/` 内のファイルを一覧取得
3. frontmatterに `processed: false` があるファイル、またはfrontmatterのないファイルを対象にする
4. 各ファイルに対して以下を実行:
   a. 内容を読んで200-500語のソース要約を生成
   b. `wiki/sources/著者-年-短タイトル.md` としてテンプレート(`templates/source-summary.md`)に従い保存
   c. 主要概念を抽出。2ソース以上に登場した概念は `wiki/concepts/` にフルページ作成/更新
   d. 重要な人物・組織は `wiki/entities/` にページ作成/更新
   e. 元ファイルのfrontmatterに `processed: true` を追加
5. `wiki/index.md` の統計を更新
6. `wiki/log.md` に操作記録を追記（日付・対象ファイル・生成ページ一覧）

## 引数

`/wiki-ingest [ファイル名]` — 特定ファイルのみ処理（省略時は全未処理ファイル）

## 出力例

```
## Ingest 完了レポート

### 処理内容
- 対象: raw/articles/example-article.md
- 生成: wiki/sources/author-2024-title.md
- 更新: wiki/index.md, wiki/log.md

### 新規概念ページ
- wiki/concepts/example-concept.md

### 発見した問題
- なし
```
