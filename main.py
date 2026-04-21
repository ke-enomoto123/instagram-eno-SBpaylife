import os
import sys
import datetime
from content.caption_generator import build_caption
from content.image_generator import generate_image
from content.news_fetcher import fetch_latest_news
from instagram.poster import post_to_instagram

def main():
    print("=" * 50)
    print(f"[Main] Instagram自動投稿開始: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[Main] 時間帯: {os.getenv('TIME_OF_DAY', 'general')}")
    print("=" * 50)

    # 0. ニュースチェック（朝の1回目のみ優先取得、他は通常）
    forced_topic = None
    news = fetch_latest_news(hours=48)
    if news:
        forced_topic = news["title"]
        print(f"[Main] ニュース優先トピック: {forced_topic[:60]}")

    # 1. キャプション生成
    result = build_caption(forced_topic=forced_topic)
    caption = result["caption"]
    score = result["score"]

    print(f"\n[Main] ===== 生成されたキャプション =====")
    print(caption)
    print(f"[Main] 文字数: {len(caption)}/2200")
    print(f"[Main] スコア: {score}/10.0")
    print("=" * 42)

    # 2. 画像生成
    save_path = "/tmp/post_image.jpg"
    image_local, image_url = generate_image(caption, save_path)
    print(f"[Main] 画像URL: {image_url[:60]}...")

    # 3. Instagram投稿
    post_id = post_to_instagram(image_url, caption)
    print(f"\n[Main] ✅ Instagram投稿完了! ID: {post_id}")

if __name__ == "__main__":
    main()
