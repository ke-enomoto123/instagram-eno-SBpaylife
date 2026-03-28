import os
import sys
import datetime
from content.caption_generator import build_caption
from content.image_generator import generate_image
from instagram.poster import post_to_instagram

def main():
    print("=" * 50)
    print(f"[Main] Instagram自動投稿開始: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[Main] 時間帯: {os.getenv('TIME_OF_DAY', 'general')}")
    print("=" * 50)

    # 1. キャプション生成
    result = build_caption()
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

    # 4. X投稿（トークンが設定されている場合のみ）
    from config import X_OAUTH2_REFRESH_TOKEN
    if X_OAUTH2_REFRESH_TOKEN:
        try:
            from x.poster import post_tweet
            # X用キャプション（280文字制限）
            x_caption = caption[:270] + "…" if len(caption) > 270 else caption
            tweet_id = post_tweet(x_caption, x_username="eno_SBpaylife")
            print(f"[Main] ✅ X投稿完了! ID: {tweet_id}")
        except Exception as e:
            print(f"[Main] ⚠️ X投稿エラー（Instagram投稿は成功済み）: {e}")
    else:
        print("[Main] X_OAUTH2_REFRESH_TOKEN 未設定 - X投稿スキップ")

if __name__ == "__main__":
    main()
