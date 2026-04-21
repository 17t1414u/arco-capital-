"""
Board meeting tasks.

Weekly board meeting that:
  1. Reviews last week's activity across all divisions (COO)
  2. Sets monthly revenue KPIs per division to hit the company target (CFO)
  3. Proposes marketing push to generate traffic (CMO)
  4. Defines "first sellable product" per division (CPO)
  5. Sanity-checks technical feasibility (CTO)
  6. CEO synthesises, approves, and issues the weekly action plan
"""

from crewai import Agent, Task

from tasks.base_task import make_task


def build_board_meeting_tasks(
    ceo_agent: Agent,
    cfo_agent: Agent,
    cto_agent: Agent,
    coo_agent: Agent,
    cmo_agent: Agent,
    cpo_agent: Agent,
    *,
    company_snapshot: str,
    revenue_target_jpy: int = 100_000,
    horizon_weeks: int = 4,
) -> list[Task]:
    """Build the ordered task list for the first board meeting."""

    common_context = (
        f"## 会社コンテキスト\n{company_snapshot}\n\n"
        f"## 今回の会議の会社目標\n"
        f"- **売上目標**: 今後 {horizon_weeks} 週間（約1ヶ月）で "
        f"累計 {revenue_target_jpy:,} 円の実収益を生み出す\n"
        f"- **リソース制約**: オーナー1名 + AIエージェント群。追加の採用・出資なし。\n"
        f"- **安全制約**: AGENTS.mdのRULE-01〜RULE-10を遵守（ペーパートレード基本・"
        f"金融商品取引法・景品表示法の範囲内の訴求）\n"
    )

    coo_review_task = make_task(
        description=(
            common_context
            + "\n---\n\n"
            "あなたはCOOとして、直近1週間の会社活動を総括してください。\n\n"
            "1. 事業部ごとに「完了したこと」「未完了のこと」「ブロッカー」を3点以内で列挙\n"
            "2. 1週間の活動がどの程度「売上創出」に近づいているかを5段階で評価（1=遠い〜5=直前）\n"
            "3. 活動のうち「測定可能なKPIが未定義」のものを全て指摘し、定量化案を提示\n"
            "4. 曖昧な目標・抽象的な作業項目は必ず列挙し、CEO裁量で削除/具体化する候補として挙げること\n\n"
            "根拠はコミットログ・ディレクトリ構造・CLAUDE.md の記述に限る。想像で補わない。"
        ),
        expected_output=(
            "マークダウンで以下の見出しを持つ週次レビュー:\n"
            "## 1週間の総括\n"
            "### 事業部別 完了/未完了/ブロッカー\n"
            "（事業部ごとのテーブルまたは箇条書き）\n"
            "### 売上創出への距離 (1-5) と根拠\n"
            "### 定量化されていない目標とその定量化案\n"
            "### 来週CEOが意思決定すべき論点リスト（最大5件）"
        ),
        agent=coo_agent,
    )

    cfo_kpi_task = make_task(
        description=(
            common_context
            + "\n---\n\n"
            "COOの週次レビューを踏まえて、CFOとして以下を行ってください:\n\n"
            f"1. 1ヶ月で {revenue_target_jpy:,} 円の売上目標を、事業部ごとに配分する\n"
            "   - 各事業部の目標金額と、その達成に必要な「単価 × 販売数 × 転換率」を具体的数値で提示\n"
            "   - 現実的に収益化可能性の低い事業部には 0 円配分も可（理由明記）\n"
            f"2. 配分の内訳は 累計 {revenue_target_jpy:,} 円になるよう算数を合わせる\n"
            "3. 各事業部KPIを「先行指標」と「遅行指標」の2層で定義\n"
            "   - 先行指標: 週次で測れる行動量（例: 投稿数・プロフィール閲覧数・LP到達数）\n"
            "   - 遅行指標: 実売上・購入数\n"
            "4. 最もROIが高い事業部を1つ選び、「集中投資すべき事業部」として推薦"
        ),
        expected_output=(
            "## 月次売上KPIの事業部別配分\n"
            "### 配分テーブル\n"
            "| 事業部 | 月次売上目標(円) | 単価 | 必要販売数 | 想定転換率 | 必要リード数 |\n"
            "### 先行指標 / 遅行指標\n"
            "（事業部ごと）\n"
            "### 集中投資推薦とその根拠\n"
            "### この配分が崩れる最大リスク"
        ),
        agent=cfo_agent,
    )

    cmo_growth_task = make_task(
        description=(
            common_context
            + "\n---\n\n"
            "CFOの事業部別KPI配分に対し、CMOとして1ヶ月で必要な"
            "リード数・フォロワー・インプレッションを生むための集客戦略を立案してください。\n\n"
            "1. X（Twitter）は既存の@RR1420597468366アカウントで運用前提\n"
            "2. 金融商品取引法・景品表示法の範囲内で「具体的投資助言にならない」表現に限定\n"
            "3. 来週（次の7日間）の具体的投稿計画（何日に何本・テーマ・フック文）を提示\n"
            "4. X以外に着手すべきチャネル（Note・YouTube Shorts・LP等）を1〜2つ厳選し、着手順と理由を明記\n"
            "5. 投稿・コンテンツ制作の自動化度合い（既存の crews/trading/x_thread_crew.py 等の再利用）を考慮"
        ),
        expected_output=(
            "## 集客戦略と来週の投稿計画\n"
            "### 必要リード逆算\n"
            "### 来週のX投稿カレンダー（曜日×本数×テーマ×フック）\n"
            "### 着手すべき追加チャネルと理由\n"
            "### コンテンツ自動化の再利用案（既存crewからの転用）\n"
            "### 違反リスク（金商法/景表法）と回避策"
        ),
        agent=cmo_agent,
    )

    cpo_product_task = make_task(
        description=(
            common_context
            + "\n---\n\n"
            "CPOとして、CFOの配分を実現するために「最初に売るべき商品」を"
            "事業部ごとに1つ定義してください。\n\n"
            "各商品について以下を明記:\n"
            "1. 商品名（仮称でも可）\n"
            "2. ターゲット顧客のペルソナ\n"
            "3. 提供価値（JTBD形式: 顧客が完了したい仕事）\n"
            "4. MVP仕様（必須機能3つまで）\n"
            "5. 販売価格と決済方法（note・BOOTH・Stripe・Gumroad等）\n"
            "6. 制作〜販売開始までの日数（目標: 14日以内）\n"
            "7. 既存のコード・ドキュメント資産でどこまで流用できるか"
        ),
        expected_output=(
            "## 事業部別 最初に売る商品\n"
            "（事業部ごとにセクション）\n"
            "- 商品名 / ペルソナ / JTBD / MVP3機能 / 価格 / 販売方法 / 制作日数 / 流用資産\n"
            "### 最優先でリリースすべき商品（1つ選定、理由）"
        ),
        agent=cpo_agent,
    )

    cto_feasibility_task = make_task(
        description=(
            common_context
            + "\n---\n\n"
            "CTOとして、CPOが提案した商品とCMOが提案したチャネル戦略の"
            "技術的実現可能性を冷静に評価してください。\n\n"
            "1. 各商品のMVP実装にかかる工数を人日で見積もる（既存資産の流用を前提）\n"
            "2. AGENTS.mdのRULE-01〜RULE-10に抵触する提案があれば列挙\n"
            "3. 自動投稿・自動売買の運用で発生しうる技術的インシデント（APIレート制限・"
            "pending注文滞留・prompt injection）をリスクとして提示\n"
            "4. 1ヶ月スパンで実装すべき/見送るべき技術投資を判定（YAGNI原則）"
        ),
        expected_output=(
            "## 技術的実現可能性レビュー\n"
            "### 商品別MVP工数（人日）\n"
            "### AGENTS.md違反の有無\n"
            "### 想定インシデントTOP3と緩和策\n"
            "### 見送るべき過剰投資"
        ),
        agent=cto_agent,
    )

    ceo_decision_task = make_task(
        description=(
            common_context
            + "\n---\n\n"
            "CEOとして、COO/CFO/CMO/CPO/CTOの提言を統合し、"
            "**来週1週間の具体的アクションプラン**と"
            "**1ヶ月後に10万円売上を達成するための事業部別KPI**を最終決定してください。\n\n"
            "出力要件:\n"
            "1. 会社全体の戦略的判断（どの事業部に集中・どれを一旦凍結するか）を1文で宣言\n"
            "2. 事業部別 月次売上KPI（CFO案を採用/修正/差し戻し、理由を明記）\n"
            "3. 来週（7日間）の日次アクションリスト（日付・担当エージェントまたは人間・完了条件）\n"
            "4. 意思決定に対するリスクと、それが顕在化したときの撤退基準\n"
            "5. この議事録を閲覧する未来の自分 or 後任CEOへの引き継ぎメモ（3行）\n\n"
            "懸念があればCOO/CFO/CMO/CPO/CTOの名前を明示して差し戻す形で質問してください。"
            "ただし、最終決定は必ず今ここで下すこと（判断保留は禁止）。"
        ),
        expected_output=(
            "# 取締役会議事録 — 決議事項\n\n"
            "## 戦略宣言（1文）\n"
            "## 事業部別 月次売上KPI（最終確定）\n"
            "## 来週のアクションプラン（日別）\n"
            "## 撤退基準\n"
            "## 後任への引き継ぎメモ（3行）\n\n"
            "末尾に Approved by: CEO / Date: {今日の日付} を記載"
        ),
        agent=ceo_agent,
        output_file="board_meeting_minutes.md",
    )

    return [
        coo_review_task,
        cfo_kpi_task,
        cmo_growth_task,
        cpo_product_task,
        cto_feasibility_task,
        ceo_decision_task,
    ]
