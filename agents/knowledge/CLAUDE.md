# Knowledge Department — Agent Guidelines

## 部門ミッション
Obsidian Knowledge Base（外部脳）の構築・維持・活用を担い、
ユーザーの調査・思考・創造を知識の複利で加速する。

## エージェント一覧と役割

| エージェント | 役割概要 |
|-------------|---------|
| Knowledge Curator | 素材の取り込み・分類・ソース要約の生成 |
| Synthesis Analyst | 複数ソースの横断分析・洞察の統合 |
| Wiki Librarian | Wikiの品質管理・Lint・インデックス維持 |

## Vault参照先

- **Vault path**: `C:/Users/17t14/Documents/Obsidian Vault/`
- **Schema**: `C:/Users/17t14/Documents/Obsidian Vault/CLAUDE.md`
- **Master Index**: `C:/Users/17t14/Documents/Obsidian Vault/wiki/index.md`
- **Activity Log**: `C:/Users/17t14/Documents/Obsidian Vault/wiki/log.md`

## 行動指針

1. **raw/ は不変**: 元素材を書き換えない。要約・加工はすべてwiki/に
2. **引用必須**: クエリ回答は必ず `[[ソースページ名]]` で根拠を示す
3. **ログ必須**: すべての操作後に `wiki/log.md` に記録を追記
4. **矛盾フラグ**: 情報の矛盾を発見したら `> ⚠️ 要確認:` で明示
5. **インデックス同期**: ページ作成・更新後は `wiki/index.md` の統計を更新

## オペレーション手順

### Ingest
```
1. raw/ の未処理ファイルを読む（processed: false のもの）
2. wiki/sources/ にソース要約を作成（テンプレート: templates/source-summary.md）
3. 概念・エンティティを抽出してWikiページを作成/更新
4. 元ファイルのfrontmatterを processed: true に更新
5. wiki/log.md に記録
```

### Query
```
1. wiki/ 全体から関連ページを収集
2. 引用付き回答を生成
3. wiki/outputs/YYYY-MM-DD-クエリ要約.md に保存
4. wiki/log.md に記録
```

### Lint
```
1. [[リンク先]] の存在確認 → 壊れたリンクを報告
2. 矛盾情報を検出 → ⚠️ フラグ
3. 6ヶ月超の情報 → 📅 要更新フラグ
4. スタブページ一覧を出力
5. ArcoCapital/ナレッジ連携事業部/reports/ にレポートを保存
```

## 出力フォーマット

```markdown
## [操作名] 完了レポート

### 処理内容
- 対象: ファイル名 / クエリ
- 生成: 新規ページ一覧
- 更新: 更新ページ一覧

### 発見した問題
- ⚠️ 矛盾: ...
- 📅 要更新: ...

### 次のアクション推奨
- [ ] ...
```
