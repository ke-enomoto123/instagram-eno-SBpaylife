"""
post_x.py
generate_x_post.py が保存した post_data_x.json を読み込んでXに投稿
"""
import os
import sys
import json
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from x.poster import post_tweet


def main():
    print("=" * 50)
    print(f"[Post X] 投稿開始: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    with open("post_data_x.json", "r", encoding="utf-8") as f:
        post_data = json.load(f)

    x_text = post_data["x_text"]
    generated_at = post_data.get("generated_at", "不明")

    print(f"[Post X] 生成日時: {generated_at}")
    print(f"[Post X] 投稿テキスト:\n{x_text}")
    print(f"[Post X] 文字数: {len(x_text)}")

    tweet_id = post_tweet(x_text, x_username="eno_SBpaylife")
    print(f"\n[Post X] ✅ X投稿完了! ID: {tweet_id}")


if __name__ == "__main__":
    main()
