# /wiki-lint — Wiki品質チェック

`wiki/` 全体の健康状態をチェックし、問題を検出・報告します。

## 手順

1. `C:/Users/17t14/Documents/Obsidian Vault/CLAUDE.md` を読んでスキーマを確認
2. 以下のチェックを実行:
   a. **壊れたリンク**: `[[リンク先]]` のファイルが存在しないものを列挙
   b. **矛盾検出**: 同じ概念について異なる説明をしているページを検出 → `> ⚠️ 要確認:` フラグ
   c. **古い情報**: 6ヶ月以上更新されていないページ → `> 📅 要更新:` フラグ
   d. **スタブページ**: 内容が200語未満のページを列挙
   e. **孤立ページ**: 他のページからリンクされていないページを列挙
3. レポートを `ArcoCapital/ナレッジ連携事業部/reports/lint-YYYY-MM-DD.md` に保存
4. `wiki/log.md` に操作記録を追記

## 出力

```markdown
# Lint レポート YYYY-MM-DD

## 壊れたリンク (N件)
- [[存在しないページ]] — 参照元: wiki/concepts/xxx.md

## 矛盾フラグ (N件)
- wiki/concepts/xxx.md vs wiki/concepts/yyy.md

## 要更新ページ (N件)
- wiki/sources/xxx.md — 最終更新: YYYY-MM-DD

## スタブページ (N件)
- wiki/concepts/xxx.md — 現在N語

## 孤立ページ (N件)
- wiki/xxx.md

## 推奨アクション
- [ ] ...
```
