import requests
import time
from config import INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID

def create_media_container(image_url: str, caption: str) -> str:
    url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"
    params = {
        "image_url": image_url,
        "caption": caption,
        "access_token": INSTAGRAM_ACCESS_TOKEN,
    }
    response = requests.post(url, params=params)
    if not response.ok:
        print(f"[Post] メディアコンテナエラー: {response.text}")
    response.raise_for_status()
    return response.json()["id"]

def publish_instagram_post(container_id: str) -> str:
    url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish"
    params = {
        "creation_id": container_id,
        "access_token": INSTAGRAM_ACCESS_TOKEN,
    }
    response = requests.post(url, params=params)
    if not response.ok:
        print(f"[Post] 公開エラー詳細: {response.text}")
    response.raise_for_status()
    return response.json()["id"]

def post_to_instagram(image_url: str, caption: str) -> str:
    print("[Post] Instagramへ投稿中...")
    container_id = create_media_container(image_url, caption)
    print(f"[Post] コンテナID: {container_id}")
    time.sleep(5)
    post_id = publish_instagram_post(container_id)
    print(f"[Post] 投稿成功! Post ID: {post_id}")
    return post_id


def _wait_container_ready(container_id: str, max_attempts: int = 12, interval: int = 5):
    """コンテナがFINISHEDになるまでポーリング"""
    url = f"https://graph.facebook.com/v19.0/{container_id}"
    params = {"fields": "status_code", "access_token": INSTAGRAM_ACCESS_TOKEN}
    for attempt in range(1, max_attempts + 1):
        resp = requests.get(url, params=params, timeout=30)
        status = resp.json().get("status_code", "")
        print(f"[Post] コンテナ状態 ({attempt}/{max_attempts}): {status}")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"コンテナ処理エラー: {resp.text}")
        time.sleep(interval)
    raise TimeoutError("カルーセルコンテナが完了しませんでした")


def post_carousel_to_instagram(image_urls: list, caption: str) -> str:
    """カルーセル投稿（2〜10枚）。1枚しかない場合は単発にフォールバック"""
    if len(image_urls) < 2:
        return post_to_instagram(image_urls[0], caption)

    image_urls = image_urls[:10]  # API上限
    print(f"[Post] カルーセル投稿中... ({len(image_urls)}枚)")

    # ① 子コンテナを作成
    children = []
    for i, img_url in enumerate(image_urls, 1):
        url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"
        params = {
            "image_url": img_url,
            "is_carousel_item": "true",
            "access_token": INSTAGRAM_ACCESS_TOKEN,
        }
        resp = requests.post(url, params=params, timeout=60)
        if not resp.ok:
            print(f"[Post] 子コンテナ{i}エラー: {resp.text}")
        resp.raise_for_status()
        children.append(resp.json()["id"])
        print(f"[Post] 子コンテナ {i}/{len(image_urls)} 作成")

    # ② 親（カルーセル）コンテナを作成
    url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"
    params = {
        "media_type": "CAROUSEL",
        "children": ",".join(children),
        "caption": caption,
        "access_token": INSTAGRAM_ACCESS_TOKEN,
    }
    resp = requests.post(url, params=params, timeout=60)
    if not resp.ok:
        print(f"[Post] カルーセルコンテナエラー: {resp.text}")
    resp.raise_for_status()
    carousel_id = resp.json()["id"]
    print(f"[Post] カルーセルコンテナ: {carousel_id}")

    # ③ 処理完了を待って公開
    _wait_container_ready(carousel_id)
    post_id = publish_instagram_post(carousel_id)
    print(f"[Post] カルーセル投稿成功! Post ID: {post_id}")
    return post_id
