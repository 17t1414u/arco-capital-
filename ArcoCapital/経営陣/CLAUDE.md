# 経営陣 — Division Schema

**所属**: Arco Capital
**設立**: 2026-04-18
**ミッション**: 会社全体の戦略方向性を決定し、各事業部に明確なKPIと週次アクションを委任する。

---

## 部門構成

| エージェント | 役割 | 実装 |
|-------------|------|------|
| CEO | 最高意思決定者・manager_agent | [agents/executive/ceo.py](../../agents/executive/ceo.py) |
| CFO | 財務戦略・ROI・KPI配分 | [agents/executive/cfo.py](../../agents/executive/cfo.py) |
| CTO | 技術的実現可能性・インシデント評価 | [agents/executive/cto.py](../../agents/executive/cto.py) |
| COO | 実行監督・週次レビュー | [agents/executive/coo.py](../../agents/executive/coo.py) |
| CMO | 集客戦略・SNS運用監督 | [agents/executive/cmo.py](../../agents/executive/cmo.py) |
| CPO | プロダクト戦略・商品定義 | [agents/executive/cpo.py](../../agents/executive/cpo.py) |

CEO は `allow_delegation=True`、その他役員は `allow_delegation=False`（循環委任防止）。

---

## クルー構成

**BoardMeetingCrew** — [crews/executive/board_meeting_crew.py](../../crews/executive/board_meeting_crew.py)

```
Process.hierarchical
  manager_agent: CEO
  agents:        [CFO, CTO, COO, CMO, CPO]
  tasks:
    1. COO 週次レビュー
    2. CFO 月次KPI配分
    3. CMO 集客戦略
    4. CPO 商品定義
    5. CTO 技術的実現可能性レビュー
    6. CEO 最終決定（議事録出力）
```

各回、`division_scanner.py` が `ArcoCapital/` 配下の事業部状況を自動スキャンし、
会社スナップショットとしてプロンプトに注入する（手動更新不要）。

---

## ディレクトリ構造

```
ArcoCapital/経営陣/
├── CLAUDE.md                  # 本ファイル
└── 取締役会議事録/
    └── YYYY-MM-DD_<議題>.md   # BoardMeetingCrew の出力が自動アーカイブされる
```

---

## 運用フロー

### 週次（毎週土曜）
```bash
# 取締役会の開催
python -c "from crews.executive.board_meeting_crew import BoardMeetingCrew; \
           print(BoardMeetingCrew(topic='週次レビュー_YYYY-MM-DD').run())"
```

1. `division_scanner` が `ArcoCapital/` をスキャン → 会社スナップショット生成
2. COO → CFO → CMO → CPO → CTO → CEO の順で発言
3. CEO が議事録を `outputs/board_meeting_minutes.md` に出力
4. `run()` が `取締役会議事録/YYYY-MM-DD_<議題>.md` へコピー

### 臨時（意思決定が必要な時）
- `topic` を明示して呼び出す（例: `BoardMeetingCrew(topic='XXX事業部の凍結判断')`）
- 議題がファイル名に反映される

---

## KPI（経営陣自身）

| 指標 | 目標 |
|------|------|
| 取締役会の開催頻度 | 週1回以上 |
| 議事録の保存率 | 100%（全会議） |
| 意思決定の曖昧さ指数 | COO レビューで「未定量」項目がゼロ |
| 撤退基準の明記率 | 全KPIに撤退条件を付与 |

---

## 行動指針（Behavioral Guidelines）

1. **データドリブン**: 意見ではなく、ファイル・コミットログ・数値に基づいて主張する
2. **BLUF**: 結論を最初に、根拠を後から
3. **リスク明示**: 推奨案を提示する際は必ずリスクと撤退基準を添える
4. **スコープ遵守**: 担当領域外の決定は上位者または担当エージェントへ委ねる
5. **日本語出力**: 議事録・意思決定ドキュメントは日本語

---

## 委任ルール

- **CEO** → 全部門への委任権限あり（`allow_delegation = True`）
- **CFO/CTO/COO/CMO/CPO** → 自部門のみ委任可。他部門宛の依頼は CEO を経由
- 循環委任（A→B→A）は禁止

---

## 禁止事項

- 根拠なき数値（「月10万円売れるはず」等の希望観測）の議事録への記載
- CEO の決定を経ずに事業部へ直接指示を出すこと
- 議事録の未保存・後付け改ざん
- AGENTS.md の RULE-01〜RULE-10 に違反する決議
