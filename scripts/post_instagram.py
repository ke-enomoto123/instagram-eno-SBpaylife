"""
post_instagram.py
generate_post.py が保存した post_data.json を読み込んでInstagramに投稿
image_urls が2枚以上あればカルーセル、1枚なら単発画像
"""
import os
import sys
import json
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from instagram.poster import post_to_instagram, post_carousel_to_instagram


def main():
    print("=" * 50)
    print(f"[Post] 投稿開始: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    with open("post_data.json", "r", encoding="utf-8") as f:
        post_data = json.load(f)

    caption = post_data["caption"]
    image_urls = post_data.get("image_urls") or [post_data["image_url"]]
    generated_at = post_data.get("generated_at", "不明")

    print(f"[Post] 生成日時: {generated_at}")
    print(f"[Post] 画像枚数: {len(image_urls)}")
    print(f"[Post] キャプション:\n{caption}")

    if len(image_urls) >= 2:
        try:
            post_id = post_carousel_to_instagram(image_urls, caption)
        except Exception as e:
            print(f"[Post] カルーセル投稿失敗 → 単発画像でリトライ: {e}")
            post_id = post_to_instagram(image_urls[0], caption)
    else:
        post_id = post_to_instagram(image_urls[0], caption)

    print(f"\n[Post] ✅ Instagram投稿完了! ID: {post_id}")


if __name__ == "__main__":
    main()
