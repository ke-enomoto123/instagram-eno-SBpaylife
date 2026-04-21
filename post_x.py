import os
import datetime
import anthropic
from content.caption_generator import build_caption
from content.news_fetcher import fetch_latest_news
from x.poster import post_tweet, post_tweet_with_image
from x.infographic_generator import generate_infographic
from config import ANTHROPIC_API_KEY


def _build_news_tweet(news: dict) -> str:
    """ニュース情報から280文字以内のXキャプションをClaudeで生成"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": f"""以下のニュースをSoftBank/PayPayユーザー向けに、X（Twitter）の投稿テキストにしてください。

ニュース: {news['title']}
概要: {news['summary'][:200]}

ルール:
- 100文字以内
- ユーザー目線で「これ知ってた？」「やばい」など親しみやすい口調
- 絵文字1〜2個
- 最後に改行して「#PayPay #SoftBank」を付ける
- 画像（インフォグラフィック）と一緒に投稿するので、画像の補足テキストとして機能させる

テキストのみ出力。"""
        }],
    )
    text = message.content[0].text.strip()
    return text[:270] + "…" if len(text) > 270 else text


def main():
    print("=" * 50)
    print(f"[X] 自動投稿開始: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[X] 時間帯: {os.getenv('TIME_OF_DAY', 'general')}")
    print("=" * 50)

    # ① ニュース取得（直近48h）
    news = fetch_latest_news(hours=48)

    if news:
        # ② ニュースあり → インフォグラフィック投稿
        print(f"\n[X] 新着ニュースあり → インフォグラフィック投稿モード")

        # インフォグラフィック画像を生成
        infographic_path = "/tmp/infographic.png"
        generate_infographic(news, save_path=infographic_path)

        # 画像に添えるテキストを生成
        x_text = _build_news_tweet(news)

        print(f"\n[X] ===== ツイートテキスト =====")
        print(x_text)
        print(f"[X] 文字数: {len(x_text)}")
        print("=" * 30)

        # 画像付きで投稿
        tweet_id = post_tweet_with_image(x_text, infographic_path, x_username="eno_SBpaylife")

    else:
        # ③ 新着なし → 通常テキスト投稿（既存ロジック）
        print(f"\n[X] 新着なし → 通常キャプション投稿モード")

        result = build_caption()
        caption = result["caption"]
        score = result["score"]

        print(f"\n[X] ===== 生成されたキャプション =====")
        print(caption)
        print(f"[X] 文字数: {len(caption)}")
        print(f"[X] スコア: {score}/10.0")
        print("=" * 42)

        x_text = caption[:270] + "…" if len(caption) > 270 else caption
        tweet_id = post_tweet(x_text, x_username="eno_SBpaylife")

    print(f"\n[X] ✅ 投稿完了! ID: {tweet_id}")


if __name__ == "__main__":
    main()
