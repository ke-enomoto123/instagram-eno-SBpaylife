"""
generate_x_post.py
Xキャプション生成 → post_data_x.json保存 → Slack通知
"""
import os
import sys
import json
import datetime
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from content.caption_generator import build_x_caption
from content.news_fetcher import fetch_latest_news

ACCOUNT_USERNAME = "@eno_SBpaylife"
ACCOUNT_NAME = "えのちゃん"


def notify_slack(x_text: str, run_url: str):
    """SlackにXキャプションをプレビュー通知"""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("[Slack] SLACK_WEBHOOK_URL未設定 → スキップ")
        return

    char_count = len(x_text)
    char_status = "✅" if char_count <= 280 else "⚠️ 文字数オーバー"

    payload = {
        "text": f"🐦 X投稿チェック依頼（{ACCOUNT_USERNAME}）",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🐦 X投稿プレビュー｜{ACCOUNT_NAME}（{ACCOUNT_USERNAME}）"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*投稿テキスト:*\n```{x_text}```"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*文字数:* {char_count} / 280　{char_status}"},
                    {"type": "mrkdwn", "text": f"*生成日時:* {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"}
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "👆 内容を確認して、GitHubで承認または却下してください"
                }
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
    }

    resp = requests.post(webhook_url, json=payload, timeout=10)
    if resp.ok:
        print("[Slack] 通知送信完了 ✅")
    else:
        print(f"[Slack] 通知エラー: {resp.status_code} {resp.text}")


def main():
    print("=" * 50)
    print(f"[Generate X] 開始: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # ニュースチェック（直近48h）
    news = fetch_latest_news(hours=48)
    forced_topic = news["title"] if news else None
    if forced_topic:
        print(f"[Generate X] ニューストピック: {forced_topic}")
    else:
        print("[Generate X] 通常トピックで生成")

    # Xキャプション生成
    result = build_x_caption(forced_topic=forced_topic)
    caption = result["caption"]
    score = result["score"]

    # 280文字以内に収める
    x_text = caption[:270] + "…" if len(caption) > 270 else caption

    print(f"\n[Generate X] キャプション:\n{x_text}")
    print(f"[Generate X] 文字数: {len(x_text)} / スコア: {score}")

    # post_data_x.json に保存
    post_data = {
        "x_text": x_text,
        "generated_at": datetime.datetime.now().isoformat(),
        "score": score,
    }
    with open("post_data_x.json", "w", encoding="utf-8") as f:
        json.dump(post_data, f, ensure_ascii=False, indent=2)
    print("[Generate X] post_data_x.json 保存完了")

    # GitHub Actions URLを構築
    server = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    repo = os.getenv("GITHUB_REPOSITORY", "ke-enomoto123/instagram-eno-SBpaylife")
    run_id = os.getenv("GITHUB_RUN_ID", "")
    run_url = f"{server}/{repo}/actions/runs/{run_id}"

    # Slack通知
    notify_slack(x_text, run_url)


if __name__ == "__main__":
    main()
