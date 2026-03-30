import os
import base64
import random
import shutil
import requests
from io import BytesIO
from openai import OpenAI
from config import OPENAI_API_KEY, IMGBB_API_KEY

NO_FACE = "IMPORTANT: Do NOT show any person's face. Show hands only, over-the-shoulder view, or focus on the smartphone screen / objects only."

DALLE_PROMPTS = [
    # PayPay・スマホ決済
    f"Close-up of woman's hands holding a smartphone showing a QR payment app (PayPay-style) at a convenience store checkout. Soft indoor lighting, natural and casual feel. {NO_FACE}",
    f"Overhead flat lay of a smartphone with a digital wallet app open, surrounded by shopping bags and a coffee cup on a white desk. Bright and minimal. {NO_FACE}",
    f"Woman's hand tapping smartphone at a cashier terminal, blurred store background, warm lighting. Everyday shopping scene. {NO_FACE}",

    # Yahoo!ショッピング・EC
    f"Hands opening a cardboard delivery box with shopping items inside, warm home interior background. Casual unboxing scene. {NO_FACE}",
    f"Smartphone screen showing an online shopping app with products, held in woman's hands, cozy home setting. {NO_FACE}",
    f"Flat lay of delivered packages, a smartphone, and a notebook on a wooden floor. Lifestyle and online shopping theme. {NO_FACE}",

    # ポイント・カード
    f"Woman's hand holding a credit card next to a smartphone showing a points balance screen. Clean white background. {NO_FACE}",
    f"Close-up of a smartphone screen displaying point rewards and cashback numbers. Soft background blur. {NO_FACE}",
    f"Flat lay of a smartphone, credit card, receipt, and small coins on a marble surface. Money saving concept. {NO_FACE}",

    # 日常・カフェ・生活
    f"Woman's hands typing on a laptop at a cafe, smartphone beside it showing a shopping app. Natural light, cozy atmosphere. {NO_FACE}",
    f"Comfortable home desk setup with smartphone showing deals/coupons screen, coffee mug, and notebook. Soft morning light. {NO_FACE}",
    f"Grocery shopping scene with a smartphone held above items in a basket, QR code visible. Supermarket setting. {NO_FACE}",

    # コンビニ
    f"Convenience store interior scene, woman's hand with smartphone near payment terminal. Bright store lighting, casual and real. {NO_FACE}",
    f"Close-up of convenience store snacks and drinks on shelf, with a smartphone showing a coupon screen. {NO_FACE}",

    # まとめ・節約
    f"Flat lay of a notebook with savings calculations, a smartphone, calculator, and pen on a desk. Budget planning concept. {NO_FACE}",
    f"Overhead shot of hands writing in a notebook next to a smartphone displaying monthly cashback summary. Clean desk setup. {NO_FACE}",
]

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
        # Pillowがない場合はそのまま読む
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

def generate_image(prompt: str, save_path: str):
    """ユーザー写真優先、なければDALL-Eで生成"""
    # ① ユーザー写真を試す
    user_photo = _get_user_photo()
    if user_photo:
        try:
            image_url = _upload_to_imgbb(user_photo)
            print(f"[Image] ユーザー写真をimgbbにアップロード完了")
            return user_photo, image_url
        except Exception as e:
            print(f"[Image] imgbbアップロード失敗: {e}")
            print("[Image] DALL-Eにフォールバック...")

    # ② DALL-Eで生成
    dalle_prompt = random.choice(DALLE_PROMPTS)
    print(f"[Image] DALL-E生成中...")

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.images.generate(
        model="dall-e-3",
        prompt=dalle_prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )

    image_url = response.data[0].url
    print(f"[Image] DALL-E URL取得完了（直接使用）")

    # ローカル保存
    img_response = requests.get(image_url, timeout=30)
    with open(save_path, 'wb') as f:
        f.write(img_response.content)

    return save_path, image_url
