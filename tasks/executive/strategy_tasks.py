"""
Phase 1 strategy tasks: CEO and CTO discuss the company's first business.

Task flow (hierarchical process):
  1. cto_analysis_task  — CTO analyzes market opportunities
  2. ceo_decision_task  — CEO synthesizes CTO's input and makes a final call

The CEO task has output_file set, so CrewAI writes the result to
outputs/discussion_result.md automatically after completion.
"""

from crewai import Agent, Task

from tasks.base_task import make_task


def build_strategy_tasks(ceo_agent: Agent, cto_agent: Agent) -> list[Task]:
    """
    Build and return the ordered task list for the executive strategy session.

    Args:
        ceo_agent: Built CEOAgent instance (the manager in hierarchical crew).
        cto_agent: Built CTOAgent instance (worker).

    Returns:
        List of Tasks in execution order.
    """

    cto_analysis_task = make_task(
        description=(
            "2025〜2026年のAI・ソフトウェア技術トレンドを分析し、"
            "この仮想会社が最初に参入すべきビジネスドメインの候補を3つ提示してください。\n\n"
            "各候補について以下を評価してください:\n"
            "1. ドメイン名と概要\n"
            "2. 市場規模と成長性 (TAM/SAM の推定)\n"
            "3. AI/技術による競合優位性の作りやすさ\n"
            "4. MVP（最小実行可能製品）の開発難易度 (1=簡単〜5=困難)\n"
            "5. 収益化までの推定期間\n"
            "6. 最大リスク要因\n\n"
            "分析は客観的かつ批判的に行い、過度に楽観的な評価は避けてください。"
        ),
        expected_output=(
            "3つのビジネスドメイン候補をマークダウン形式で構造化したレポート。"
            "各候補には: ドメイン名・市場規模・技術的優位性・MVP難易度（1-5）・"
            "収益化期間・最大リスクが含まれていること。"
            "最後に、技術的観点から最も推薦する候補と理由を1段落で述べること。"
        ),
        agent=cto_agent,
    )

    ceo_decision_task = make_task(
        description=(
            "CTOの技術分析レポートを受け取りました。\n\n"
            "以下のビジネス戦略基準でCTOの3候補を評価・検討してください:\n"
            "- 収益ポテンシャルと事業継続性\n"
            "- 市場への参入タイミング（先行者優位 vs 追随リスク）\n"
            "- チーム・リソース適合性\n"
            "- 競合との差別化ポイント\n\n"
            "CTOの技術的見解に対して、ビジネス視点から補足質問・懸念点を提示し、"
            "それを踏まえた上で最終的なビジネス方向性を1つ選定してください。\n\n"
            "結論は明確な根拠とともに、すぐに実行に移せる形で提示してください。"
        ),
        expected_output=(
            "CEOとしての最終意思決定ドキュメント（マークダウン形式）:\n"
            "1. 選定したビジネス方向性とミッションステートメント（1文）\n"
            "2. 選定理由（戦略的根拠を箇条書き3〜5点）\n"
            "3. CTOの技術分析で特に重視した点\n"
            "4. 懸念点とその対処方針\n"
            "5. 会社としての直近のネクストステップ（3〜5項目）"
        ),
        agent=ceo_agent,
        output_file="discussion_result.md",
    )

    return [cto_analysis_task, ceo_decision_task]
