import os
import datetime
from content.caption_generator import build_caption
from x.poster import post_tweet

def main():
    print("=" * 50)
    print(f"[X] 自動投稿開始: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[X] 時間帯: {os.getenv('TIME_OF_DAY', 'general')}")
    print("=" * 50)

    # キャプション生成
    result = build_caption()
    caption = result["caption"]
    score = result["score"]

    print(f"\n[X] ===== 生成されたキャプション =====")
    print(caption)
    print(f"[X] 文字数: {len(caption)}")
    print(f"[X] スコア: {score}/10.0")
    print("=" * 42)

    # X用に280文字以内に収める
    x_text = caption[:270] + "…" if len(caption) > 270 else caption

    # X投稿
    tweet_id = post_tweet(x_text, x_username="eno_SBpaylife")
    print(f"\n[X] ✅ 投稿完了! ID: {tweet_id}")

if __name__ == "__main__":
    main()
