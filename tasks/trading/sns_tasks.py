"""
SNSコンテンツ生成タスク — SNSReporterAgent 用

make_market_news_post_task()  — マーケット情報のSNS投稿生成
make_trade_result_post_task() — トレード結果のSNS投稿生成
make_monthly_summary_post_task() — 月次実績サマリー投稿生成
"""

from tasks.base_task import make_task


def make_market_news_post_task(market_context: str, agent):
    """
    マーケット情報・投資関連ニュースのSNS投稿を生成するタスク。

    Args:
        market_context: 市場データ・ニュース情報テキスト
        agent:          SNSReporterAgent.build() で生成したエージェント
    """
    return make_task(
        description=f"""
以下のマーケット情報をもとに、X(Twitter)用の投稿テキストを3パターン生成してください。

【マーケット情報】
{market_context}

【投稿生成ルール】
1. 各パターンは140文字以内（日本語）
2. 絵文字を効果的に使用する（1〜3個）
3. 必ず #株式投資 #ArcoCapital のハッシュタグを含める
4. 投資勧誘表現（「〜を買え」「〜は必ず上がる」等）は使用しない
5. 「〜の可能性があります」「〜と思われます」など推測表現を使用する
6. 数値（指数値・変動率）を含めると説得力が増す

【投稿タイプ別】
- パターンA: 相場概況型（今日の市場全体）
- パターンB: 注目銘柄型（特定の銘柄にフォーカス）
- パターンC: 投資知識型（学びになる情報）

【対象アカウント】
X: @RR1420597468366
""",
        expected_output="""
X投稿テキストを3パターン日本語で生成する:

---
【パターンA: 相場概況】
[140文字以内の投稿テキスト。絵文字・数値・ハッシュタグ含む]

---
【パターンB: 注目銘柄】
[140文字以内の投稿テキスト。絵文字・数値・ハッシュタグ含む]

---
【パターンC: 投資知識】
[140文字以内の投稿テキスト。絵文字・ハッシュタグ含む]

---
【推奨投稿パターン】
パターン[A/B/C] — 理由: [選択理由]
""",
        agent=agent,
        output_file="sns_market_news.md",
    )


def make_trade_result_post_task(trade_data: dict, agent):
    """
    トレード結果のSNS投稿を生成するタスク。

    Args:
        trade_data: 取引データ辞書
                    {ticker, action, entry_price, exit_price,
                     pnl_pct, pnl_usd, comment}
        agent:      SNSReporterAgent.build() で生成したエージェント
    """
    trade_text = "\n".join(f"- {k}: {v}" for k, v in trade_data.items())

    return make_task(
        description=f"""
以下のトレード結果を、X(Twitter)用の投稿テキストに変換してください。

【取引データ】
{trade_text}

【投稿生成ルール】
1. 140文字以内（日本語）
2. 損益率と損益金額（USD）を明記する
3. 利益の場合: 📈 絵文字を使用し、ポジティブなトーン
4. 損失の場合: 📉 絵文字を使用し、学びや次への意気込みを添える
5. 「ペーパートレード」の場合はその旨を明記する
6. 必ず #株式投資 #自動売買 #ArcoCapital タグを含める
7. 具体的な投資アドバイスは含めない
""",
        expected_output="""
X投稿テキストを日本語で生成する:

---
【投稿テキスト】
[140文字以内。絵文字・損益数値・ハッシュタグ含む]
---

【補足コメント（投稿には含めない）】
[投稿の意図・注意点など]
""",
        agent=agent,
        output_file="sns_trade_result.md",
    )


def make_monthly_summary_post_task(monthly_stats: dict, agent):
    """
    月次実績サマリーのSNS投稿を生成するタスク。

    Args:
        monthly_stats: 月次統計辞書
                       {month, trade_count, win_rate, monthly_pnl_pct,
                        best_trade, worst_trade, total_pnl_usd}
        agent:         SNSReporterAgent.build() で生成したエージェント
    """
    stats_text = "\n".join(f"- {k}: {v}" for k, v in monthly_stats.items())

    return make_task(
        description=f"""
以下の月次実績データをもとに、月次サマリーのSNS投稿テキストを生成してください。

【月次データ】
{stats_text}

【投稿要件】
1. 月次サマリーは少し長めでも良い（最大280文字）
2. 主要KPI（取引数・勝率・月次損益）を必ず含める
3. 最高パフォーマンス銘柄をハイライトする
4. 来月への展望や意気込みを一言添える
5. 必ず #株式投資 #資産運用 #ArcoCapital タグを含める
6. ペーパートレードか本番かを明記する
""",
        expected_output="""
月次サマリーX投稿テキストを日本語で生成する:

---
【月次サマリー投稿】
[280文字以内。KPI数値・絵文字・ハッシュタグ含む]
---

【スレッド用追加投稿（オプション）】
[詳細を補足するリプライ投稿案 140文字以内]
""",
        agent=agent,
        output_file="sns_monthly_summary.md",
    )
