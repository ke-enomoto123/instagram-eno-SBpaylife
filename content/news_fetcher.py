import feedparser
from datetime import datetime, timedelta, timezone
from typing import Optional

JST = timezone(timedelta(hours=9))

# Google News RSS（無料・APIキー不要）
NEWS_FEEDS = [
    ("PayPayキャンペーン", "https://news.google.com/rss/search?q=PayPay+キャンペーン+特典&hl=ja&gl=JP&ceid=JP:ja"),
    ("SoftBank特典", "https://news.google.com/rss/search?q=SoftBank+特典+ポイント+割引&hl=ja&gl=JP&ceid=JP:ja"),
    ("LYPプレミアム", "https://news.google.com/rss/search?q=LYPプレミアム+特典+サービス&hl=ja&gl=JP&ceid=JP:ja"),
    ("PayPayカード還元", "https://news.google.com/rss/search?q=PayPayカード+還元+キャッシュバック&hl=ja&gl=JP&ceid=JP:ja"),
    ("Yahooショッピング", "https://news.google.com/rss/search?q=Yahooショッピング+ポイント+キャンペーン&hl=ja&gl=JP&ceid=JP:ja"),
]

# 除外キーワード（関係ないニュースを弾く）
EXCLUDE_KEYWORDS = ["詐欺", "不正", "障害", "メンテナンス", "訴訟", "事故"]


def _parse_published(entry) -> Optional[datetime]:
    pub = entry.get("published_parsed")
    if not pub:
        return None
    return datetime(*pub[:6], tzinfo=timezone.utc).astimezone(JST)


def _is_relevant(title: str, summary: str) -> bool:
    text = title + summary
    return not any(kw in text for kw in EXCLUDE_KEYWORDS)


def fetch_latest_news(hours: int = 48) -> Optional[dict]:
    """
    直近 hours 時間以内の SoftBank/PayPay 関連ニュースを取得。
    新着なければ None を返す。
    """
    cutoff = datetime.now(JST) - timedelta(hours=hours)
    found = []

    for category, url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                pub_dt = _parse_published(entry)
                if pub_dt and pub_dt > cutoff:
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")[:400]
                    if _is_relevant(title, summary):
                        found.append({
                            "category": category,
                            "title": title,
                            "summary": summary,
                            "link": entry.get("link", ""),
                            "published": pub_dt.strftime("%Y-%m-%d %H:%M"),
                        })
        except Exception as e:
            print(f"[News] RSS取得エラー ({category}): {e}")

    if not found:
        print("[News] 直近48h以内の新着なし → 通常トピックで投稿")
        return None

    # 最新1件を返す
    found.sort(key=lambda x: x["published"], reverse=True)
    news = found[0]
    print(f"[News] 新着ニュース: [{news['category']}] {news['title'][:60]}")
    print(f"[News] 公開日時: {news['published']}")
    return news
