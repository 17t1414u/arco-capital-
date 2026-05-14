"""
SNS動画運用事業部 Week1 タスク定義。

Director (manager_agent) が以下の4役割に委任する:
  - VideoPlanner    : cinematic-everyday-01 の企画書 (project.json + 絵コンテ)
  - VideoGenerator  : Renoise セグメント生成 (¥10k/週上限)
  - VideoEditor     : ffmpeg 結合・BGM・ラウドネス -14 LUFS
  - SalesAgent      : 制作代行 LP 草案 + DM 返信テンプレ

出力先: outputs/sns_video/week1_*.md (環境設定 settings.output_dir 経由)
"""

from crewai import Agent, Task

from tasks.base_task import make_task


def build_sns_video_week1_tasks(
    *,
    director: Agent,
    planner: Agent,
    generator: Agent,
    editor: Agent,
    sales: Agent,
    project_slug: str = "cinematic-everyday-01",
    renoise_weekly_cap_jpy: int = 10_000,
    api_daily_cap_jpy: int = 1_500,
) -> list[Task]:
    """Build hierarchical Week1 tasks for SNS動画運用事業部."""

    guardrail_note = (
        f"\n\n## ガードレール (RULE-04 遵守)\n"
        f"- Renoise クレジット: **週次 ¥{renoise_weekly_cap_jpy:,} ハードキャップ**\n"
        f"- Anthropic API: **日次 ¥{api_daily_cap_jpy:,} 上限**\n"
        f"- 超過は `operations/kill_switch.py --trigger budget_breach` で自動停止\n"
        f"- モード B: 最終納品・公開前に必ずオーナー承認 (承認キュー滞留 15 分以内)\n"
        f"- ブランド毀損・誇大表現は禁止 (景品表示法遵守)\n"
    )

    plan_task = make_task(
        description=(
            f"## プロジェクト {project_slug} の企画確定\n\n"
            "VideoPlanner として以下を成果物にすること:\n\n"
            "1. `ArcoCapital/SNS動画運用事業部/企画/" + project_slug + "/project.json` を更新\n"
            "   - shots配列: 3セグ以上、各 duration / aspect 9:16 / prompt 必須\n"
            "   - BGM 候補: 著作権フリー (YouTube Audio Library / Uppbeat) のみ\n"
            "2. 絵コンテ Markdown を同ディレクトリに作成\n"
            "   - 各ショットの構図・被写体・動き・テロップ案 (日本語)\n"
            "3. 顔出しゼロ: 手・シルエット・物の寄りで物語る縦型文法を徹底\n"
            "4. 商用利用可能な要素のみで構成 (他社素材の無断使用ゼロ)\n"
            + guardrail_note
        ),
        expected_output=(
            "## 企画確定レポート\n"
            "- project.json 更新サマリ (shot数・合計duration)\n"
            "- 絵コンテ本体 (Markdown でそのまま貼り付け)\n"
            "- 著作権チェック結果 (OK/NG)\n"
            "- 次ステップ (VideoGenerator への引き継ぎ事項)"
        ),
        agent=planner,
        output_file=f"sns_video/week1_plan_{project_slug}.md",
    )

    generate_task = make_task(
        description=(
            f"## {project_slug} のセグメント生成\n\n"
            "VideoGenerator として以下を実行:\n\n"
            "1. 企画確定レポートの project.json を入力に Renoise でセグメント生成\n"
            "2. 1ショットあたり最大 2 リトライ。失敗は `operations/incident_log.jsonl` に追記\n"
            f"3. 週次 ¥{renoise_weekly_cap_jpy:,} ハードキャップを超える場合は中断して Director に報告\n"
            "4. 成功したショットのファイルパス + 消費クレジット額を `operations/budget_log.jsonl` に記録\n"
            "5. Renoise 例外処理・リトライ境界・回路遮断の **設計書草案** (Markdown) を添付\n"
            + guardrail_note
        ),
        expected_output=(
            "## セグメント生成レポート\n"
            "- 生成成功ショット一覧 (パス + 秒数 + 消費クレジット)\n"
            "- 失敗ショットとエラー内容\n"
            "- 消費額合計 / 残り予算\n"
            "- Renoise 例外処理設計書草案 (Markdown、セクション: トリガー / リトライ / Kill-switch連動)"
        ),
        agent=generator,
        output_file=f"sns_video/week1_generate_{project_slug}.md",
    )
    generate_task.context = [plan_task]

    edit_task = make_task(
        description=(
            f"## {project_slug} の最終編集\n\n"
            "VideoEditor として以下を実行:\n\n"
            "1. 生成レポートのセグメントを `concat.txt` で結合\n"
            "2. 著作権フリー BGM を合成 (YouTube Audio Library / Uppbeat)\n"
            "3. テロップ合成 (ASS/SRT)、日本語は細明朝または細ゴシック\n"
            "4. ラウドネス正規化 -14 LUFS (YouTube Shorts 推奨)\n"
            "5. 最終成果物を `ArcoCapital/SNS動画運用事業部/実績/2026-04/" + project_slug + "_final.mp4` に保存\n"
            + guardrail_note
        ),
        expected_output=(
            "## 最終編集レポート\n"
            "- 出力ファイルパス (mp4) + サイズ + 秒数\n"
            "- BGM タイトル + ライセンス URL\n"
            "- ラウドネス計測値 (LUFS)\n"
            "- オーナー承認依頼 (モード B の必須フロー)"
        ),
        agent=editor,
        output_file=f"sns_video/week1_edit_{project_slug}.md",
    )
    edit_task.context = [plan_task, generate_task]

    sales_task = make_task(
        description=(
            "## 制作代行 LP 草案 + DM 返信テンプレ\n\n"
            "SalesAgent として以下を成果物にすること:\n\n"
            "1. 制作代行 LP 草案 (note or HP 想定、Before/After/Bridge 構造)\n"
            "   - 価格帯: 30秒 ¥15,000 / 15秒×3本 ¥30,000\n"
            "   - 納期: 最長 7 営業日\n"
            "   - 禁止: 「必ず集客が増える」等の断定表現 (景品表示法)\n"
            "2. DM 初回返信テンプレ (24h 以内 SLO 遵守)\n"
            "3. 見積書テンプレ (Excel or Markdown)\n"
            "4. 特商法表記の下書き (必須事項: 販売事業者・所在地・連絡先・返金)\n"
            + guardrail_note
        ),
        expected_output=(
            "## 営業素材一式\n"
            "- LP 草案 (Markdown、2000-3000字)\n"
            "- DM 初回返信テンプレ (3パターン: 新規問合/見積依頼/カジュアル)\n"
            "- 見積書テンプレ (価格表付き)\n"
            "- 特商法表記ドラフト\n"
            "- 送信前オーナー承認チェックリスト"
        ),
        agent=sales,
        output_file="sns_video/week1_sales_kit.md",
    )

    director_task = make_task(
        description=(
            "## Week1 総括とオーナー承認依頼\n\n"
            "SNSVideoDirector として以下を統合すること:\n\n"
            "1. 4タスク (企画・生成・編集・営業) の成果物サマリを1枚にまとめる\n"
            "2. Phase 1 ゲート (4/25) の 3条件達成可否:\n"
            "   - CINEMATIC_01: cinematic-everyday-01 完成\n"
            "   - RENDER_DESIGN: Renoise 例外処理設計書 PR 化\n"
            "   - AGENCY_LP: 制作代行 LP 公開準備\n"
            "3. 消費予算サマリ (Renoise / API それぞれの累計と残額)\n"
            "4. オーナー承認が必要な送信・公開項目の一覧\n"
            "5. 未達項目と CEO/CTO へのエスカレーション事項\n"
            + guardrail_note
        ),
        expected_output=(
            "## Week1 総括レポート\n"
            "- 4タスク成果物リンク一覧\n"
            "- Phase 1 ゲート 3条件の達成率 (%)\n"
            "- 消費予算スナップショット\n"
            "- オーナー承認待ちアイテム (チェックリスト形式)\n"
            "- 経営陣へのエスカレーション事項 (最大3件)"
        ),
        agent=director,
        output_file="sns_video/week1_director_summary.md",
    )
    director_task.context = [plan_task, generate_task, edit_task, sales_task]

    return [plan_task, generate_task, edit_task, sales_task, director_task]
