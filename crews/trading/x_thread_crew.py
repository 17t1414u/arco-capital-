"""
XInvestmentThreadCrew — X投資スレッド自動投稿クルー

毎朝7:30 JSTに実行し、5投稿のリプライチェーンを作成する。

スレッド構造:
  投稿1 (メイン): HOOK + ハッシュタグ (#米国株 #投資 #S&P500 #株式投資 #資産運用)
  └ 返信2: 背景 — なぜこうなった？
     └ 返信3: 原因分析 — どうしてこういうことが起きた？
        └ 返信4: 相場予測 — 今後の相場はどうなる？
           └ 返信5: 投資戦略 — 自分はどう動けばいい？ + CTA

フロー:
  1. ニュース収集 (Alpaca News API + RSS)
  2. スレッド原稿生成 (Claude Anthropic API → JSON)
  3. 画像生成 (Nano Banana Pro / gemini-3-pro-image-preview)
  4. X投稿 (tweepy v1 media upload + v2 create_tweet)

使用例:
    # ドライラン（投稿なし・確認のみ）
    crew = XInvestmentThreadCrew(dry_run=True)
    result = crew.run()

    # 本番投稿
    crew = XInvestmentThreadCrew(dry_run=False)
    result = crew.run()
"""

import io
import json
import os
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from config.settings import settings

# --- ブランドカラー ---
BRAND_DARK   = "#0A0F1E"   # 背景（ダークネイビー）
BRAND_CYAN   = "#00D4FF"   # アクセント（シアン）
BRAND_GOLD   = "#FFD700"   # ハイライト（ゴールド）
BRAND_WHITE  = "#FFFFFF"

# --- ハッシュタグ（投稿1のみ） ---
HASHTAGS = "#米国株 #投資 #S&P500 #株式投資 #資産運用"

# --- 1投稿あたりの目安文字数（日本語 + 英語混在 = 140文字換算） ---
MAX_CHARS_PER_POST = 230   # 余裕を持たせた上限


class XInvestmentThreadCrew:
    """
    X投資スレッド自動投稿クルー。

    Args:
        dry_run:   True = 投稿せずログ出力のみ（デフォルト: True）
        topic:     テーマを手動指定（空文字 = ニュースから自動選択）
    """

    def __init__(self, dry_run: bool = True, topic: str = ""):
        self.dry_run = dry_run
        self.topic = topic

    # ──────────────────────────────────────────────────────────────────────────
    # PUBLIC: メインエントリーポイント
    # ──────────────────────────────────────────────────────────────────────────

    def run(self) -> str:
        """
        スレッド全体を実行し、結果サマリーを返す。
        """
        today = date.today().strftime("%Y年%m月%d日")
        mode_str = "🔍 ドライラン（投稿なし）" if self.dry_run else "🚀 本番投稿モード"

        _print_header(f"XInvestmentThreadCrew 起動 — {today}")
        print(f"  モード: {mode_str}\n")

        # STEP 1: ニュース収集
        print("📰 STEP 1/4: ニュース収集中...\n")
        news_text = self._fetch_news()
        print(f"   → {len(news_text)} 文字のニュースを収集\n")

        # STEP 2: スレッド原稿生成
        print("✍️  STEP 2/4: スレッド原稿生成中 (Claude)...\n")
        posts = self._generate_thread_scripts(news_text)
        _preview_posts(posts)

        # STEP 3: 画像生成
        print("🎨 STEP 3/4: 画像生成中 (Nano Banana Pro)...\n")
        image_paths = self._generate_images(posts)
        print(f"   → {len(image_paths)} 枚の画像を生成\n")

        # STEP 4: X投稿
        if self.dry_run:
            print("📋 STEP 4/4: ドライランのため投稿をスキップします\n")
            thread_url = "（ドライラン — 実際の投稿なし）"
        else:
            print("🐦 STEP 4/4: X にスレッドを投稿中...\n")
            thread_url = self._post_thread(posts, image_paths)

        # 結果保存
        result = self._save_result(today, posts, thread_url)
        _print_header("XInvestmentThreadCrew 完了")
        print(f"  スレッドURL: {thread_url}\n")

        # 一時ファイルをクリーンアップ
        _cleanup_images(image_paths)

        return result

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 1: ニュース収集
    # ──────────────────────────────────────────────────────────────────────────

    def _fetch_news(self) -> str:
        """
        Alpaca News API + RSS フィードからニュースを収集する。
        手動トピックが指定されている場合はそのまま返す。
        """
        if self.topic:
            return f"【指定テーマ】\n{self.topic}"

        news_items = []

        # Alpaca News API
        news_items.extend(self._fetch_alpaca_news())

        # RSS フィード（フォールバック）
        if len(news_items) < 5:
            news_items.extend(self._fetch_rss_news())

        if not news_items:
            return _get_default_market_context()

        lines = ["【本日の主要マーケットニュース】\n"]
        for i, item in enumerate(news_items[:10], 1):
            lines.append(f"{i}. {item}")
        return "\n".join(lines)

    def _fetch_alpaca_news(self) -> list[str]:
        """Alpaca News API から直近ニュースを取得する"""
        try:
            from alpaca.data import StockHistoricalDataClient
            from alpaca.data.requests import StockNewsRequest

            client = StockHistoricalDataClient(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_secret_key,
            )
            end = date.today()
            start = end - timedelta(days=2)
            request = StockNewsRequest(
                symbols=["SPY", "QQQ", "AAPL", "NVDA", "MSFT", "TSLA", "AMZN"],
                start=start,
                end=end,
                limit=20,
            )
            news = client.get_news(request)

            items = []
            seen = set()
            for article in news:
                headline = getattr(article, "headline", "") or ""
                summary = getattr(article, "summary", "") or ""
                if headline and headline not in seen:
                    seen.add(headline)
                    items.append(f"{headline}　{summary[:100]}" if summary else headline)
            return items

        except Exception as e:
            print(f"   ⚠️ Alpaca News API エラー: {e}")
            return []

    def _fetch_rss_news(self) -> list[str]:
        """Yahoo Finance / Reuters RSSからニュースをフェッチする"""
        try:
            import urllib.request
            import xml.etree.ElementTree as ET

            feeds = [
                "https://finance.yahoo.com/news/rssindex",
                "https://feeds.reuters.com/reuters/businessNews",
            ]
            items = []
            for url in feeds:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        tree = ET.parse(resp)
                    for item in tree.iter("item"):
                        title = item.findtext("title") or ""
                        if title:
                            items.append(title)
                        if len(items) >= 10:
                            break
                except Exception:
                    continue
            return items
        except Exception as e:
            print(f"   ⚠️ RSS フェッチエラー: {e}")
            return []

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 2: スレッド原稿生成
    # ──────────────────────────────────────────────────────────────────────────

    def _generate_thread_scripts(self, news_text: str) -> list[dict]:
        """
        Claude API を使って5投稿分のスレッド原稿を生成する。

        Returns:
            list of dict: [
                {"index": 1, "role": "HOOK", "text": "...", "image_prompt": "..."},
                ...
            ]
        """
        today = date.today().strftime("%Y年%m月%d日")

        system_prompt = """あなたはArco Capitalの投資コンテンツライターです。
日本語で、米国株に興味を持つ投資家向けのXスレッドを作成します。

【出力形式】必ずJSON配列で返してください。
[
  {
    "index": 1,
    "role": "HOOK",
    "text": "投稿テキスト（ハッシュタグ含む）",
    "image_prompt": "英語の画像生成プロンプト"
  },
  ...
]

【ルール】
- 投稿1のみハッシュタグを末尾に追加: #米国株 #投資 #S&P500 #株式投資 #資産運用
- 各投稿は200文字以内（日本語）
- 絵文字を効果的に使う（各投稿1〜3個）
- 数字・データを具体的に入れる
- 読者を次の投稿に引きつけるフック
- image_promptは50〜80単語の英語で、ダークネイビー背景(#0A0F1E)・シアン(#00D4FF)・ゴールド(#FFD700)のブランドカラーを使用"""

        user_prompt = f"""今日 {today} のマーケットニュースをもとに、
以下の5ポスト構成でXスレッドを作成してください。

【ニュース情報】
{news_text}

【5投稿の役割】
1. HOOK: 読者を引きつける衝撃的な一言・数字・問いかけ
2. 背景 (Why?): なぜこのことが起きているのか？背景・文脈を説明
3. 原因分析 (How?): 具体的な原因・メカニズムを深掘り
4. 相場予測 (Outlook?): 今後1〜4週間の相場シナリオ（強気/弱気）
5. 投資戦略 (Action?): 具体的な行動提案 + フォローCTA

必ずJSON形式のみで返答してください（```json ブロック不要）。"""

        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt,
        )

        raw = message.content[0].text.strip()

        # JSON抽出（```json ブロックが含まれる場合に対応）
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        posts = json.loads(raw)

        # バリデーション
        for i, post in enumerate(posts):
            if "text" not in post:
                raise ValueError(f"投稿 {i+1} に 'text' キーがありません")
            # 投稿1のハッシュタグが含まれていない場合は追加
            if post.get("index", i + 1) == 1 and HASHTAGS not in post["text"]:
                post["text"] = post["text"].rstrip() + f"\n\n{HASHTAGS}"

        return posts[:5]  # 最大5投稿

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 3: 画像生成
    # ──────────────────────────────────────────────────────────────────────────

    def _generate_images(self, posts: list[dict]) -> list[Optional[str]]:
        """
        各投稿に対して Nano Banana Pro (Gemini) で画像を生成する。

        Returns:
            list[Optional[str]]: 一時ファイルパスのリスト（失敗時は None）
        """
        image_paths: list[Optional[str]] = []

        for post in posts:
            idx = post.get("index", len(image_paths) + 1)
            role = post.get("role", f"Post{idx}")
            img_prompt = post.get(
                "image_prompt",
                f"Financial investment chart, dark navy background, cyan accents, "
                f"professional typography, {role} concept",
            )

            print(f"   🎨 画像生成中: [{idx}/5] {role}...")
            path = self._generate_single_image(idx, img_prompt)
            image_paths.append(path)

            if path:
                print(f"      ✅ 保存: {path}")
            else:
                print(f"      ⚠️ 生成失敗（テキストのみで投稿）")

            # レート制限対策
            if idx < 5:
                time.sleep(3)

        return image_paths

    def _generate_single_image(self, idx: int, prompt: str) -> Optional[str]:
        """
        Nano Banana Pro で1枚の画像を生成し、一時ファイルに保存する。
        """
        try:
            from google import genai
            from google.genai import types

            google_api_key = os.getenv("GOOGLE_API_KEY", "")
            if not google_api_key:
                raise EnvironmentError("GOOGLE_API_KEY が未設定です")

            client = genai.Client(api_key=google_api_key)

            full_prompt = (
                f"{prompt}. "
                "Style: premium financial infographic. "
                f"Brand colors: dark navy background ({BRAND_DARK}), "
                f"cyan accent ({BRAND_CYAN}), gold highlight ({BRAND_GOLD}). "
                "Clean, modern, professional. No text overlay. "
                "Aspect ratio 16:9."
            )

            response = client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"]
                ),
            )

            # レスポンスから画像データを取得
            for part in response.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    image_data = part.inline_data.data
                    if isinstance(image_data, str):
                        import base64
                        image_data = base64.b64decode(image_data)

                    # 一時ファイルに保存
                    tmp = tempfile.NamedTemporaryFile(
                        suffix=f"_arco_post{idx}.png",
                        delete=False,
                    )
                    tmp.write(image_data)
                    tmp.close()
                    return tmp.name

            return None

        except Exception as e:
            print(f"      ⚠️ 画像生成エラー (post {idx}): {e}")
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 4: X投稿
    # ──────────────────────────────────────────────────────────────────────────

    def _post_thread(
        self,
        posts: list[dict],
        image_paths: list[Optional[str]],
    ) -> str:
        """
        tweepy v1（メディアアップロード）+ v2（ツイート作成）でスレッドを投稿する。

        Returns:
            str: スレッドの最初のツイートURL
        """
        import tweepy

        # --- tweepy v1 (media upload) ---
        auth = tweepy.OAuth1UserHandler(
            consumer_key=settings.x_api_key,
            consumer_secret=settings.x_api_secret,
            access_token=settings.x_access_token,
            access_token_secret=settings.x_access_token_secret,
        )
        api_v1 = tweepy.API(auth)

        # --- tweepy v2 (tweet creation) ---
        client_v2 = tweepy.Client(
            consumer_key=settings.x_api_key,
            consumer_secret=settings.x_api_secret,
            access_token=settings.x_access_token,
            access_token_secret=settings.x_access_token_secret,
            wait_on_rate_limit=True,
        )

        first_tweet_id: Optional[str] = None
        reply_to_id: Optional[str] = None

        for i, post in enumerate(posts):
            text = post["text"]
            img_path = image_paths[i] if i < len(image_paths) else None

            # 画像をアップロード
            media_ids = None
            if img_path and Path(img_path).exists():
                try:
                    media = api_v1.media_upload(filename=img_path)
                    media_ids = [media.media_id_string]
                    print(f"   📸 メディアアップロード完了: post {i+1}")
                except Exception as e:
                    print(f"   ⚠️ メディアアップロード失敗 (post {i+1}): {e}")

            # ツイート作成
            kwargs: dict = {"text": text}
            if media_ids:
                kwargs["media_ids"] = media_ids
            if reply_to_id:
                kwargs["in_reply_to_tweet_id"] = reply_to_id

            try:
                response = client_v2.create_tweet(**kwargs)
                tweet_id = response.data["id"]
                print(f"   ✅ 投稿完了: post {i+1} (id={tweet_id})")

                if first_tweet_id is None:
                    first_tweet_id = tweet_id
                reply_to_id = tweet_id

            except Exception as e:
                print(f"   ❌ 投稿エラー (post {i+1}): {e}")
                raise

            # レート制限対策（連続投稿は2秒待機）
            if i < len(posts) - 1:
                time.sleep(2)

        handle = settings.x_account_handle
        thread_url = (
            f"https://x.com/{handle}/status/{first_tweet_id}"
            if first_tweet_id else "（投稿ID取得失敗）"
        )
        return thread_url

    # ──────────────────────────────────────────────────────────────────────────
    # 結果保存
    # ──────────────────────────────────────────────────────────────────────────

    def _save_result(self, today: str, posts: list[dict], thread_url: str) -> str:
        """
        スレッド内容を ArcoCapital/資産運用事業部/SNS投稿/queue/ に保存する。
        """
        lines = [
            f"# X投資スレッド — {today}",
            f"**モード**: {'ドライラン' if self.dry_run else '本番投稿'}",
            f"**スレッドURL**: {thread_url}",
            "",
        ]
        for post in posts:
            idx = post.get("index", "?")
            role = post.get("role", "")
            text = post.get("text", "")
            lines += [
                f"## 投稿{idx}: {role}",
                text,
                "",
            ]

        result = "\n".join(lines)

        save_dir = settings.investment_division_dir / "SNS投稿" / "queue"
        save_dir.mkdir(parents=True, exist_ok=True)
        file_date = date.today().isoformat()
        save_path = save_dir / f"{file_date}_x_thread.md"
        save_path.write_text(result, encoding="utf-8")
        print(f"📄 スレッド内容を保存: {save_path}")

        return result


# ──────────────────────────────────────────────────────────────────────────────
# ヘルパー関数
# ──────────────────────────────────────────────────────────────────────────────

def _print_header(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def _preview_posts(posts: list[dict]) -> None:
    """生成された原稿をプレビュー表示する"""
    print("\n📝 生成されたスレッド原稿:\n" + "-" * 50)
    for post in posts:
        idx = post.get("index", "?")
        role = post.get("role", "")
        text = post.get("text", "")
        char_count = len(text)
        status = "⚠️ 長すぎ" if char_count > MAX_CHARS_PER_POST else "✅"
        print(f"\n【投稿{idx}: {role}】({char_count}文字 {status})")
        print(text)
    print("\n" + "-" * 50 + "\n")


def _get_default_market_context() -> str:
    """ニュース取得が失敗した場合のデフォルトコンテキスト"""
    today = date.today().strftime("%Y年%m月%d日")
    return (
        f"【{today} マーケット情報】\n"
        "ニュースデータの取得に失敗したため、一般的な投資知識ベースのコンテンツを作成してください。\n"
        "ウォッチリスト: AAPL, MSFT, NVDA, TSLA, AMZN, SPY, QQQ\n"
        "テーマ候補: 米国株の長期投資、分散投資の重要性、テクニカル分析入門、"
        "インデックス投資 vs 個別株、ドルコスト平均法"
    )


def _cleanup_images(image_paths: list[Optional[str]]) -> None:
    """生成した一時画像ファイルを削除する"""
    for path in image_paths:
        if path:
            try:
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass
