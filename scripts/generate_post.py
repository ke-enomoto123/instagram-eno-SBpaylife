"""
generate_post.py
ニュースチェック → キャプション生成 → カルーセル生成（表紙=gpt-image-2 + 中身=PILスライド）
→ imgbb保存 → Slack通知（Instagram＋X両方）
"""
import os
import sys
import json
import base64
import datetime
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from content.caption_generator import build_caption, build_x_caption
from content.image_generator import generate_image
from content.news_fetcher import fetch_latest_news
from content.carousel_generator import build_carousel_slides


ACCOUNT_USERNAME = "@eno_sbpaylife"
ACCOUNT_NAME = "えのちゃん"


def upload_to_imgbb(image_path: str) -> str:
    """画像をimgbbにアップロードして永続URLを返す"""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    resp = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": os.getenv("IMGBB_API_KEY"), "image": b64},
        timeout=30,
    )
    resp.raise_for_status()
    url = resp.json()["data"]["url"]
    print(f"[imgbb] アップロード完了: {url[:60]}...")
    return url


def notify_slack(caption: str, image_urls: list, x_text: str, run_url: str):
    """SlackにInstagram（カルーセル）＋Xのプレビューを通知"""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("[Slack] SLACK_WEBHOOK_URL未設定 → スキップ")
        return

    x_char = len(x_text)
    x_status = "✅" if x_char <= 280 else "⚠️ 文字数オーバー"
    n = len(image_urls)
    format_label = f"カルーセル {n}枚" if n >= 2 else "単発画像"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📸🐦 投稿プレビュー｜{ACCOUNT_NAME}（{ACCOUNT_USERNAME}）"}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*形式:* {format_label}\n*📸 Instagramキャプション:*\n```" + caption + "```"}
        },
    ]

    for i, url in enumerate(image_urls[:4]):
        label = "表紙" if i == 0 else f"スライド{i}"
        blocks.append({
            "type": "image",
            "image_url": url,
            "alt_text": f"{label}プレビュー",
            "title": {"type": "plain_text", "text": f"{label} ({i+1}/{n})"},
        })
    if n > 4:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"…ほか{n - 4}枚（全{n}枚のカルーセル）"}
        })

    blocks += [
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*🐦 X投稿テキスト:*\n```{x_text}```"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*X文字数:* {x_char} / 280　{x_status}"},
                {"type": "mrkdwn", "text": "*(表紙画像をXにも投稿します)*"}
            ]
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "👆 内容を確認して、GitHubで承認または却下してください"}
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ GitHubで承認・却下する"},
                    "style": "primary",
                    "url": run_url
                }
            ]
        }
    ]

    payload = {
        "text": f"📸🐦 Instagram＋X投稿チェック依頼（{ACCOUNT_USERNAME}）",
        "blocks": blocks,
    }

    resp = requests.post(webhook_url, json=payload, timeout=10)
    if resp.ok:
        print("[Slack] 通知送信完了 ✅")
    else:
        print(f"[Slack] 通知エラー: {resp.status_code} {resp.text}")


def main():
    print("=" * 50)
    print(f"[Generate] 開始: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # ニュースチェック → 優先トピック
    news = fetch_latest_news(hours=48)
    forced_topic = news["title"] if news else None

    # Instagramキャプション生成
    result = build_caption(forced_topic=forced_topic)
    caption = result["caption"]
    topic = result.get("topic", "")
    print(f"\n[Generate] キャプション:\n{caption}")
    print(f"[Generate] 文字数: {len(caption)} / スコア: {result['score']}")

    # X用テキスト生成（X専用の短いキャプション）
    x_result = build_x_caption(forced_topic=forced_topic)
    x_text = x_result["caption"]
    print(f"\n[Generate] X用テキスト:\n{x_text}")

    # 表紙画像生成（gpt-image-2）
    cover_path = "/tmp/post_image.png"
    image_local, fallback_url = generate_image(caption, cover_path)

    # カルーセルスライド生成（PIL。失敗時は単発画像にフォールバック）
    slide_paths = None
    try:
        slide_paths, structure = build_carousel_slides(
            caption=caption, topic=topic,
            cover_path=image_local, handle=ACCOUNT_USERNAME,
        )
    except Exception as e:
        print(f"[Carousel] スライド生成エラー → 単発画像で続行: {e}")

    if not slide_paths:
        slide_paths = [image_local]

    # 全スライドをimgbbにアップロード
    image_urls = []
    for p in slide_paths:
        try:
            image_urls.append(upload_to_imgbb(p))
        except Exception as e:
            print(f"[imgbb] {p} アップロード失敗: {e}")
    if not image_urls:
        image_urls = [fallback_url] if fallback_url else []
    if not image_urls:
        raise RuntimeError("画像URLを1枚も確保できませんでした")

    # post_data.json に保存（post jobで使用）
    post_data = {
        "caption": caption,
        "image_url": image_urls[0],       # 表紙（X投稿・後方互換用）
        "image_urls": image_urls,          # カルーセル全枚数
        "x_text": x_text,
        "generated_at": datetime.datetime.now().isoformat(),
    }
    with open("post_data.json", "w", encoding="utf-8") as f:
        json.dump(post_data, f, ensure_ascii=False, indent=2)
    print(f"[Generate] post_data.json 保存完了（画像{len(image_urls)}枚）")

    # GitHub Actions URLを構築
    server = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    repo = os.getenv("GITHUB_REPOSITORY", "ke-enomoto123/instagram-eno-SBpaylife")
    run_id = os.getenv("GITHUB_RUN_ID", "")
    run_url = f"{server}/{repo}/actions/runs/{run_id}"

    # Slack通知（Instagram＋X両方）
    notify_slack(caption, image_urls, x_text, run_url)


if __name__ == "__main__":
    main()
