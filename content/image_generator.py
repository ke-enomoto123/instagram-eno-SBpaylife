import os
import base64
import shutil
import requests
from io import BytesIO
from openai import OpenAI
from config import OPENAI_API_KEY, IMGBB_API_KEY

# アカウント設定
ACCOUNT_HANDLE = "@eno_sbpaylife"
BRAND_COLOR = "red (#FF0027)"
BRAND_THEME = "PayPay / SoftBank / LYPプレミアム"


def _build_infographic_prompt(caption: str) -> str:
    """キャプションからインフォグラフィック用プロンプトを生成"""
    return f"""
Create a clean, modern Japanese infographic image in 1:1 square format for Instagram.

Design style:
- Flat design, NOT photographic, NOT artistic illustration
- White or very light gray background
- Bold, readable Japanese text
- Accent color: {BRAND_COLOR}
- Modern sans-serif font style

Layout (top to bottom):
1. Header bar (full width, {BRAND_COLOR} background): Title text in white, large and bold
2. Main content area: 3 to 4 key benefit points, each on its own row
   - Each row: colored circle icon or checkmark on the left, Japanese text on the right
   - Most important number or percentage displayed in extra-large font, highlighted
3. Thin divider line
4. Footer: "{ACCOUNT_HANDLE}" in small gray text, right-aligned

Content to display — extract the 3 to 4 most important points from this caption:
\"\"\"
{caption[:600]}
\"\"\"

Important rules:
- All text must be in Japanese
- Numbers and percentages must be accurate and prominently displayed
- Do NOT add any decorative illustrations, people, or photos
- Keep it simple and easy to read at a glance
- This is an informational graphic, not art
"""


def _convert_to_jpeg(image_path: str) -> bytes:
    """画像をJPEGに変換（PNG→JPEG対応）"""
    try:
        from PIL import Image
        img = Image.open(image_path)
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=95)
        return buffer.getvalue()
    except ImportError:
        with open(image_path, 'rb') as f:
            return f.read()


def _get_user_photo() -> str | None:
    """photos/フォルダから未使用の写真を取得"""
    photos_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "photos")
    used_dir = os.path.join(photos_dir, "used")
    os.makedirs(used_dir, exist_ok=True)

    extensions = ('.jpg', '.jpeg', '.png', '.webp')
    photos = sorted([
        f for f in os.listdir(photos_dir)
        if f.lower().endswith(extensions) and os.path.isfile(os.path.join(photos_dir, f))
    ])

    if not photos:
        return None

    selected = photos[0]
    photo_path = os.path.join(photos_dir, selected)
    used_path = os.path.join(used_dir, selected)
    shutil.move(photo_path, used_path)
    print(f"[Image] ユーザー写真を使用: {selected}")
    return used_path


def _upload_to_imgbb(image_path: str) -> str:
    """JPEG変換してimgbbにアップロード、URLを返す"""
    jpeg_data = _convert_to_jpeg(image_path)
    encoded = base64.b64encode(jpeg_data).decode('utf-8')

    response = requests.post(
        "https://api.imgbb.com/1/upload",
        data={
            "key": IMGBB_API_KEY,
            "image": encoded,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()["data"]
    return data["display_url"]


def generate_image(caption: str, save_path: str):
    """ユーザー写真優先、なければgpt-image-1でインフォグラフィック生成"""
    # ① ユーザー写真を試す
    user_photo = _get_user_photo()
    if user_photo:
        try:
            image_url = _upload_to_imgbb(user_photo)
            print(f"[Image] ユーザー写真をimgbbにアップロード完了")
            return user_photo, image_url
        except Exception as e:
            print(f"[Image] imgbbアップロード失敗: {e}")
            print("[Image] gpt-image-1にフォールバック...")

    # ② gpt-image-1でインフォグラフィック生成
    infographic_prompt = _build_infographic_prompt(caption)
    print(f"[Image] gpt-image-1でインフォグラフィック生成中...")

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.images.generate(
        model="gpt-image-1",
        prompt=infographic_prompt,
        size="1024x1024",
        quality="medium",
        n=1,
    )

    # base64デコードして保存
    image_data = base64.b64decode(response.data[0].b64_json)
    with open(save_path, 'wb') as f:
        f.write(image_data)
    print(f"[Image] gpt-image-1 生成完了 → {save_path}")

    # imgbbにアップロード
    try:
        image_url = _upload_to_imgbb(save_path)
        print(f"[Image] imgbbアップロード完了")
    except Exception as e:
        print(f"[Image] imgbbアップロード失敗: {e}")
        image_url = None

    return save_path, image_url
