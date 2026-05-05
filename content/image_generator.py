import os
import json
import base64
import shutil
import requests
from io import BytesIO
from openai import OpenAI
import anthropic
from config import OPENAI_API_KEY, IMGBB_API_KEY, ANTHROPIC_API_KEY

# アカウント設定
ACCOUNT_HANDLE = "@eno_sbpaylife"
BRAND_COLOR_HEX = "#FF0027"
BRAND_COLOR_NAME = "PayPay red"


def _analyze_caption(caption: str) -> dict:
    """Claudeでキャプションを分析してビジュアルコンセプトを生成"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=600,
        messages=[{
            "role": "user",
            "content": f"""以下のInstagram投稿テキストを読んで、イラスト画像のビジュアルコンセプトをJSONで出力してください。

投稿テキスト:
{caption}

出力形式（JSONのみ。説明不要）:
{{
  "title": "画像上部に表示するキャッチコピー（20文字以内）",
  "key_number": "最も目立たせたい数字や割合（例: 月額0円、5%還元）",
  "happy_scene": "SoftBankユーザーが得している様子（英語で、イラスト指示として。例: a cheerful person pumping fist with coins flying around）",
  "sad_scene": "知らない人が損している様子（英語で。例: a confused person looking at an expensive bill with empty wallet）",
  "visual_element": "お得さを表す装飾要素（英語で。例: golden coins raining down, upward arrow graph, star burst effects）"
}}"""
        }]
    )

    text = response.content[0].text.strip()
    # コードブロックがあれば除去
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except Exception:
                continue
    return json.loads(text)


def _build_infographic_prompt(caption: str) -> str:
    """キャプションを分析してイラスト型プロンプトを生成"""
    try:
        concept = _analyze_caption(caption)
        title = concept.get("title", "SoftBankユーザーは得してる！")
        key_number = concept.get("key_number", "")
        happy_scene = concept.get("happy_scene", "a cheerful person holding smartphone with coins flying around")
        sad_scene = concept.get("sad_scene", "a confused person with empty wallet looking sad")
        visual_element = concept.get("visual_element", "golden coins, star bursts, upward arrows")
        print(f"[Image] ビジュアルコンセプト: {concept}")
    except Exception as e:
        print(f"[Image] キャプション分析失敗、デフォルト使用: {e}")
        title = "知らないと損！SoftBankのお得技"
        key_number = ""
        happy_scene = "a cheerful person holding smartphone with coins flying around, big smile"
        sad_scene = "a confused sad person looking at expensive bill with empty wallet"
        visual_element = "golden coins raining down, upward arrow graph, star burst effects"

    key_number_instruction = f'- In the CENTER or TOP area, display this key number/stat in VERY LARGE bold text inside a colored badge: "{key_number}"' if key_number else ""

    return f"""
Create a vibrant, eye-catching Japanese social media illustration (1:1 square, 1024x1024px, Instagram format).

Art style:
- Modern flat illustration, similar to Japanese app UI illustrations or LINE sticker style
- Simple, friendly cartoon characters with expressive emotions (no detailed realistic faces)
- Bold, clean Japanese text overlaid on the scene
- Bright, energetic colors with high contrast

Scene layout:
- LEFT HALF: {happy_scene}. Label below in Japanese bold text: "SoftBankユーザー✨"
- RIGHT HALF: {sad_scene}. Label below in Japanese bold text: "知らないと損！"
- A clear visual divider (lightning bolt or arrow) between the two halves
{key_number_instruction}
- TOP BANNER: Bold red banner with white Japanese text: "{title}"
- BOTTOM: Small text "{ACCOUNT_HANDLE}" in light gray

Decorative elements scattered around: {visual_element}

Color palette:
- Primary red: {BRAND_COLOR_HEX} (for banners, badges, accents)
- Bright yellow: for coins, highlights, star bursts
- Light blue or green: for positive/happy side background
- Light gray or pale pink: for sad/losing side background
- White: main background

Typography:
- All Japanese text must be clearly readable
- Title and key number in BOLD, large font
- Character labels in medium bold font

Make it instantly communicate: "SoftBankユーザーはこんなにお得！知らないと絶対損！"
Fun, energetic, scroll-stopping visual — NOT a boring text chart.
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
    print(f"[Image] gpt-image-2でインフォグラフィック生成中...")

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.images.generate(
        model="gpt-image-2",
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
