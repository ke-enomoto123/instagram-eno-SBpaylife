import base64
import os
import re
import requests
from config import X_OAUTH2_CLIENT_ID, X_OAUTH2_CLIENT_SECRET, X_OAUTH2_REFRESH_TOKEN


def _tweet_weight(text: str) -> int:
    """X (Twitter) の重み付き文字数を計算（CJKは2、Latin系は1）"""
    weight = 0
    for ch in text:
        cp = ord(ch)
        if (0x0000 <= cp <= 0x10FF) or \
           (0x2000 <= cp <= 0x200D) or \
           (0x2010 <= cp <= 0x201F) or \
           (0x2032 <= cp <= 0x2037):
            weight += 1
        else:
            weight += 2
    return weight


def _truncate_for_x(text: str, max_weight: int = 270) -> str:
    """重み付き文字数で max_weight 以内に収める。文末記号で切れるよう優先。"""
    if _tweet_weight(text) <= max_weight:
        return text
    parts = re.split(r"(\n+|。|！|？)", text)
    chunks = []
    cur = ""
    for p in parts:
        if not p:
            continue
        if re.fullmatch(r"\n+|。|！|？", p):
            cur += p
            chunks.append(cur)
            cur = ""
        else:
            cur += p
    if cur:
        chunks.append(cur)
    result = ""
    for chunk in chunks:
        if _tweet_weight(result + chunk) <= max_weight:
            result += chunk
        else:
            break
    if not result.strip():
        weight = 0
        idx = len(text)
        for i, ch in enumerate(text):
            cp = ord(ch)
            cw = 1 if (0x0000 <= cp <= 0x10FF) or \
                      (0x2000 <= cp <= 0x200D) or \
                      (0x2010 <= cp <= 0x201F) or \
                      (0x2032 <= cp <= 0x2037) else 2
            if weight + cw > max_weight:
                idx = i
                break
            weight += cw
        return text[:idx].rstrip()
    return result.rstrip()


def _update_github_secret(new_refresh_token: str):
    """新しいリフレッシュトークンをGitHub Secretsに自動保存"""
    try:
        from nacl import encoding, public

        github_token = os.getenv("GH_PAT")
        repo = os.getenv("GITHUB_REPOSITORY", "ke-enomoto123/instagram-eno-SBpaylife")

        if not github_token:
            print("[X] GH_PAT なし - Secret更新スキップ")
            return

        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        # 公開鍵を取得
        key_resp = requests.get(
            f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
            headers=headers,
        )
        key_data = key_resp.json()

        # 暗号化
        pub_key = public.PublicKey(key_data["key"].encode("utf-8"), encoding.Base64Encoder())
        encrypted = base64.b64encode(
            public.SealedBox(pub_key).encrypt(new_refresh_token.encode("utf-8"))
        ).decode("utf-8")

        # Secret更新
        resp = requests.put(
            f"https://api.github.com/repos/{repo}/actions/secrets/X_OAUTH2_REFRESH_TOKEN",
            headers=headers,
            json={"encrypted_value": encrypted, "key_id": key_data["key_id"]},
        )
        if resp.ok:
            print("[X] リフレッシュトークンを自動更新しました ✅")
        else:
            print(f"[X] Secret更新失敗: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[X] Secret更新エラー（続行）: {e}")


def _get_access_token() -> str:
    """リフレッシュトークンを使って新しいアクセストークンを取得"""
    response = requests.post(
        "https://api.x.com/2/oauth2/token",
        auth=(X_OAUTH2_CLIENT_ID, X_OAUTH2_CLIENT_SECRET),
        data={
            "grant_type": "refresh_token",
            "refresh_token": X_OAUTH2_REFRESH_TOKEN,
        },
    )
    if not response.ok:
        print(f"[X] トークン取得エラー: {response.text}")
    response.raise_for_status()

    data = response.json()
    access_token = data["access_token"]

    new_refresh_token = data.get("refresh_token")
    if new_refresh_token:
        print(f"[X] 新しいリフレッシュトークンを取得 → GitHub Secretsに保存中...")
        _update_github_secret(new_refresh_token)

    return access_token


def _upload_media_v1(image_path: str) -> str | None:
    """OAuth 1.0a + v1.1 メディアアップロード（Pay Per Use Free フォールバック用）"""
    api_key = os.getenv("X_API_KEY", "")
    api_secret = os.getenv("X_API_SECRET", "")
    access_token = os.getenv("X_ACCESS_TOKEN", "")
    access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET", "")

    if not all([api_key, api_secret, access_token, access_token_secret]):
        print("[X] OAuth 1.0a 認証情報未設定 → v1.1 fallback skip")
        return None

    try:
        import tweepy
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
        api = tweepy.API(auth)
        print(f"[X] v1.1 でメディアアップロード中: {image_path}")
        media = api.media_upload(filename=image_path)
        media_id = str(media.media_id)
        print(f"[X] v1.1 アップロード完了: media_id={media_id}")
        return media_id
    except Exception as e:
        print(f"[X] v1.1 アップロードエラー: {e}")
        return None


def _upload_media(image_path: str, access_token: str) -> str:
    """画像をX v2 Media Upload APIでアップロードし media_id を返す"""
    print(f"[X] 画像アップロード中: {image_path}")

    # v2エンドポイントで試す
    with open(image_path, "rb") as f:
        image_data = f.read()

    # MIMEタイプ判定
    mime_type = "image/jpeg"
    if image_path.lower().endswith(".png"):
        mime_type = "image/png"
    elif image_path.lower().endswith(".gif"):
        mime_type = "image/gif"

    response = requests.post(
        "https://api.x.com/2/media/upload",
        headers={"Authorization": f"Bearer {access_token}"},
        files={"media": (os.path.basename(image_path), image_data, mime_type)},
        timeout=60,
    )

    if not response.ok:
        print(f"[X] v2アップロードエラー: {response.status_code} {response.text}")
        response.raise_for_status()

    data = response.json()
    # v2レスポンスは data.id
    media_id = str(data.get("data", {}).get("id") or data.get("media_id") or data["id"])
    print(f"[X] 画像アップロード完了: media_id={media_id}")
    return media_id


def post_tweet(text: str, x_username: str = "eno_sbpaylife") -> str:
    """X（Twitter）にテキストのみのツイートを投稿する。重み280超は自動truncate。"""
    original_weight = _tweet_weight(text)
    if original_weight > 280:
        text = _truncate_for_x(text, max_weight=270)
        print(f"[X] 重み{original_weight} → {_tweet_weight(text)} に文末記号でtruncate")
    print(f"[X] ツイート投稿開始...")
    print(f"[X] 文字数: {len(text)} 重み: {_tweet_weight(text)}")
    print(f"[X] 内容: {text[:60]}...")

    access_token = _get_access_token()
    print(f"[X] アクセストークン取得完了")

    response = requests.post(
        "https://api.x.com/2/tweets",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={"text": text},
        timeout=30,
    )

    if not response.ok:
        print(f"[X] 投稿エラー詳細: {response.text}")
    response.raise_for_status()

    tweet_id = str(response.json()["data"]["id"])
    print(f"[X] 投稿完了! Tweet ID: {tweet_id}")
    print(f"[X] URL: https://x.com/{x_username}/status/{tweet_id}")
    return tweet_id


def post_tweet_with_image(text: str, image_path: str, x_username: str = "eno_sbpaylife") -> str:
    """X（Twitter）に画像付きツイートを投稿する。v2失敗時はv1.1 fallback、両方失敗ならテキストのみで投稿。重み280超は自動truncate。"""
    original_weight = _tweet_weight(text)
    if original_weight > 280:
        text = _truncate_for_x(text, max_weight=270)
        print(f"[X] 重み{original_weight} → {_tweet_weight(text)} に文末記号でtruncate")
    print(f"[X] 画像付きツイート投稿開始...")
    print(f"[X] 文字数: {len(text)} 重み: {_tweet_weight(text)}")
    print(f"[X] 内容: {text[:60]}...")

    access_token = _get_access_token()
    print(f"[X] アクセストークン取得完了")

    media_id = None
    try:
        media_id = _upload_media(image_path, access_token)
    except Exception as e:
        print(f"[X] v2画像アップロード失敗: {e}")
        print("[X] OAuth 1.0a + v1.1 でフォールバック試行")
        media_id = _upload_media_v1(image_path)
        if not media_id:
            print("[X] 画像アップロードフォールバックも失敗、テキストのみで継続")

    payload: dict = {"text": text}
    if media_id:
        payload["media"] = {"media_ids": [media_id]}

    response = requests.post(
        "https://api.x.com/2/tweets",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    if not response.ok:
        print(f"[X] 投稿エラー詳細: {response.text}")
    response.raise_for_status()

    tweet_id = str(response.json()["data"]["id"])
    print(f"[X] 投稿完了! Tweet ID: {tweet_id} (image={'あり' if media_id else 'なし'})")
    print(f"[X] URL: https://x.com/{x_username}/status/{tweet_id}")
    return tweet_id
