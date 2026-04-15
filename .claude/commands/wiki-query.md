# /wiki-query — 知識ベースへの質問

Obsidian Vault の `wiki/` を横断検索して、引用付きの回答を生成・保存します。

## 手順

1. `C:/Users/17t14/Documents/Obsidian Vault/CLAUDE.md` を読んでスキーマを確認
2. `wiki/index.md` を読んで利用可能なページの全体像を把握
3. クエリに関連する `wiki/` 内のページを収集・読み込み
4. 収集した知識を統合し、`[[ページ名]]` 引用付きの回答を生成
5. 回答を `wiki/outputs/YYYY-MM-DD-クエリ要約.md` に保存
6. `wiki/index.md` のクエリ出力セクションを更新
7. `wiki/log.md` に操作記録を追記

## 引数

`/wiki-query <質問内容>` — 質問を続けて書く

例: `/wiki-query AIエージェントアーキテクチャの最新トレンドを教えて`

## 注意

- Vaultに情報がない場合は「まだVaultにこのトピックの情報がない」と明示し、`raw/` への追加を提案する
- 情報が古い可能性がある場合は `📅 要更新` を付記する
