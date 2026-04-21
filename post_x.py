import os
import datetime
from content.caption_generator import build_x_caption
from content.news_fetcher import fetch_latest_news
from x.poster import post_tweet


def main():
    print("=" * 50)
    print(f"[X] 自動投稿開始: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[X] 時間帯: {os.getenv('TIME_OF_DAY', 'general')}")
    print("=" * 50)

    # ニュースチェック（直近48h）→ あれば優先トピックに
    news = fetch_latest_news(hours=48)
    forced_topic = news["title"] if news else None

    # キャプション生成（X専用：短くシンプル）
    result = build_x_caption(forced_topic=forced_topic)
    caption = result["caption"]
    score = result["score"]

    print(f"\n[X] ===== 生成されたキャプション =====")
    print(caption)
    print(f"[X] 文字数: {len(caption)}")
    print(f"[X] スコア: {score}/10.0")
    print("=" * 42)

    # X用に270文字以内に収める
    x_text = caption[:270] + "…" if len(caption) > 270 else caption

    # 投稿
    tweet_id = post_tweet(x_text, x_username="eno_SBpaylife")
    print(f"\n[X] ✅ 投稿完了! ID: {tweet_id}")


if __name__ == "__main__":
    main()
