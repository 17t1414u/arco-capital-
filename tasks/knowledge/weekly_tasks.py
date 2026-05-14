"""
ナレッジ連携事業部 Week1 タスク定義。

Director が以下に委任:
  - KnowledgeCurator  : raw/ の素材を wiki/sources/ に整理
  - SynthesisAnalyst  : 複数ソース横断で商品化可能な洞察を3本抽出
  - TemplateAuthor    : 洞察をテンプレパック v1 + note LP に落とし込む (4/23 厳守)
"""

from crewai import Agent, Task

from tasks.base_task import make_task


def build_knowledge_week1_tasks(
    *,
    director: Agent,
    curator: Agent,
    analyst: Agent,
    author: Agent,
    pack_title: str = "Obsidian × Claude Code 外部脳スターターキット v1.0",
    price_jpy: int = 2_980,
    api_daily_cap_jpy: int = 1_500,
) -> list[Task]:

    guardrail_note = (
        f"\n\n## ガードレール (RULE-04 遵守)\n"
        f"- Anthropic API: **日次 ¥{api_daily_cap_jpy:,} 上限** (超過で Kill-switch)\n"
        f"- モード B: 外部送信・公開前に必ずオーナー承認\n"
        f"- 景品表示法: 「必ず稼げる」等の断定表現禁止\n"
    )

    curate_task = make_task(
        description=(
            "## raw/ の素材取り込み (Week1)\n\n"
            "KnowledgeCurator として以下を実行:\n\n"
            "1. Vault `raw/` 配下で `processed: false` のファイルを最大 10 件取り込む\n"
            "2. `wiki/sources/<slug>.md` に各素材のソース要約を作成\n"
            "   - 本文の主張 / 暗黙の前提 / 引用元 / 反証可能性 の 4 軸\n"
            "3. 概念・エンティティを `[[Wikilink]]` で既存 Wiki に接続\n"
            "4. 元ファイルの frontmatter を `processed: true` に更新\n"
            "5. `wiki/log.md` に処理履歴を追記\n"
            "6. `wiki/index.md` の統計 (ページ数・最終更新) を同期\n"
            + guardrail_note
        ),
        expected_output=(
            "## 取り込みレポート\n"
            "- 取り込み件数 / スキップ件数\n"
            "- 新規 sources ページ一覧\n"
            "- 更新した既存 Wiki ページ\n"
            "- `⚠️ 要確認:` フラグを立てた矛盾"
        ),
        agent=curator,
        output_file="knowledge/week1_ingest.md",
    )

    synthesize_task = make_task(
        description=(
            "## 商品化可能な洞察 3本抽出\n\n"
            "SynthesisAnalyst として以下を実行:\n\n"
            "1. 取り込みレポートを踏まえ、Wiki 全体を横断して商品化テーマを3本選定\n"
            "2. 各テーマに対して:\n"
            "   - 既存テンプレ (Obsidian 上で再利用可能な .md 骨格)\n"
            "   - 具体的な事例 3 本 (Vault 内の [[ソース]] 引用付き)\n"
            "   - 反証パターン 1 本 (「このテンプレが効かない例」)\n"
            "3. 各テーマの想定ターゲット (職種 + 困りごと) を言語化\n"
            f"4. ¥{price_jpy} 帯で販売可能な粒度か評価 (Go / Hold / No-Go)\n"
            + guardrail_note
        ),
        expected_output=(
            "## 洞察抽出レポート\n"
            "- テーマA/B/C それぞれについて:\n"
            "  - タイトル / ターゲット / 既存テンプレ / 事例3本 / 反証\n"
            "  - 販売判断 (Go/Hold/No-Go) + 理由\n"
            "- TemplateAuthor への引き継ぎ指示 (どのテーマを優先するか)"
        ),
        agent=analyst,
        output_file="knowledge/week1_synthesis.md",
    )
    synthesize_task.context = [curate_task]

    author_task = make_task(
        description=(
            f"## {pack_title} + note LP 執筆 (4/23 厳守)\n\n"
            "TemplateAuthor として以下を実行:\n\n"
            "1. 洞察抽出レポートの Go 判定テーマから テンプレ 3 本を執筆\n"
            "   - 1テンプレ = Markdown 500-1000字 + 使い方ブロック + 具体例2つ\n"
            "2. note LP 文案 (BLUF / Before-After / 具体例 3 / CTA)\n"
            f"   - 販売価格: ¥{price_jpy:,}\n"
            "   - LP 長さ: 2000-3000字\n"
            "   - 断定表現禁止 (景品表示法): 「必ず」「絶対」「100%」を使わない\n"
            "3. 特商法表記ドラフト (販売事業者・所在地・連絡先・返金)\n"
            "4. note 公開オーナー承認用チェックリスト\n"
            + guardrail_note
        ),
        expected_output=(
            "## 商品化パッケージ一式\n"
            "- テンプレ 3 本 (Markdown 本文)\n"
            "- note LP 草案 (2000-3000字)\n"
            "- 特商法表記\n"
            "- 承認チェックリスト (モード B: 公開前に必須)\n"
            "- 使い方デモ動画の台本 (任意、VideoPlanner と連携可)"
        ),
        agent=author,
        output_file="knowledge/week1_author.md",
    )
    author_task.context = [synthesize_task]

    director_task = make_task(
        description=(
            "## Week1 総括 + オーナー承認依頼\n\n"
            "KnowledgeDirector として以下を統合すること:\n\n"
            "1. 3タスク (取り込み・洞察・商品化) の成果物サマリを1枚にまとめる\n"
            "2. Phase 1 ゲート (4/25) の 3条件:\n"
            "   - TEMPLATE_V1: テンプレパック v1 完成 (3テンプレ以上)\n"
            "   - NOTE_LP_KNOWLEDGE: note LP 公開 (**4/23 厳守**)\n"
            "   - WIKI_OPS: /wiki-ingest + /wiki-lint 週次運用 (7日連続)\n"
            "3. 4/23 公開のカウントダウンと残タスク\n"
            "4. オーナー承認が必要な項目 (note LP 本文・特商法表記・価格)\n"
            + guardrail_note
        ),
        expected_output=(
            "## Week1 総括レポート\n"
            "- 3タスク成果物リンク\n"
            "- Phase 1 ゲート達成率\n"
            "- 4/23 公開前オーナー承認チェックリスト\n"
            "- 経営陣へのエスカレーション事項"
        ),
        agent=director,
        output_file="knowledge/week1_director_summary.md",
    )
    director_task.context = [curate_task, synthesize_task, author_task]

    return [curate_task, synthesize_task, author_task, director_task]
