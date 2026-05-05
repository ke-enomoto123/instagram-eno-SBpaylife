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


def _analyze_caption(caption: str) -> dict:
    """Claudeでキャプションを広告バナー用コンセプトに分析"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": f"""以下のInstagram投稿テキストを読んで、魅力的な広告バナー画像のコンセプトをJSONで出力してください。
画像はYahoo!ショッピング・PayPay・SoftBank・LYPプレミアムなどのお得情報を訴求するもので、
実際の広告バナーのように魅力的に仕上げます。

投稿テキスト:
{caption}

出力形式（JSONのみ。説明不要）:
{{
  "main_headline": "最も目立たせるメインコピー（15文字以内、インパクト重視）",
  "sub_headline": "サブコピー（25文字以内）",
  "key_stat": "強調したい数字・特典（例: ポイント3倍、月額0円、5%還元）",
  "featured_service": "メインで見せるサービス名（例: Yahoo!ショッピング, PayPay, LYPプレミアム）",
  "event_trigger": "日付・期間・イベント名があれば（例: 5のつく日, 毎週日曜, 今月末まで。なければ空文字）",
  "visual_objects": "画像内に描くべきオブジェクト（英語で。例: smartphone showing Yahoo Shopping app, red shopping bag, golden coins, LYP premium badge, SoftBank logo）",
  "mood": "画像の雰囲気（excited/warm/premium のどれか）"
}}"""
        }]
    )

    text = response.content[0].text.strip()
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
    """キャプションを分析して広告バナー型プロンプトを生成"""
    try:
        c = _analyze_caption(caption)
        main_headline  = c.get("main_headline", "知らないと損！")
        sub_headline   = c.get("sub_headline", "SoftBankユーザー限定のお得情報")
        key_stat       = c.get("key_stat", "")
        featured       = c.get("featured_service", "Yahoo!ショッピング")
        event_trigger  = c.get("event_trigger", "")
        visual_objects = c.get("visual_objects", "smartphone showing shopping app, golden coins, red shopping bag")
        mood           = c.get("mood", "excited")
        print(f"[Image] 広告コンセプト: {c}")
    except Exception as e:
        print(f"[Image] キャプション分析失敗、デフォルト使用: {e}")
        main_headline  = "知らないと損！"
        sub_headline   = "SoftBankユーザー限定のお得情報"
        key_stat       = ""
        featured       = "Yahoo!ショッピング"
        event_trigger  = ""
        visual_objects = "smartphone showing Yahoo Shopping app, golden coins, red shopping bag, SoftBank logo"
        mood           = "excited"

    event_block = f'- TOP-RIGHT CORNER: A bold calendar or badge icon with Japanese text: "{event_trigger}"' if event_trigger else ""

    key_stat_block = f'- A large starburst or badge shape with Japanese text "{key_stat}" in huge bold font, placed prominently' if key_stat else ""

    mood_desc = {
        "excited": "bright, energetic, high-contrast — red and yellow dominant, white background with sunburst lines",
        "warm":    "warm tones, friendly — orange and yellow palette, soft gradient background",
        "premium": "clean and sophisticated — deep navy or dark background with gold and white accents",
    }.get(mood, "bright, energetic, high-contrast — red and yellow dominant, white background with sunburst lines")

    return f"""
Create a high-quality Japanese promotional banner image (1:1 square, 1024x1024px) for Instagram.
Style: professional Japanese advertisement graphic, like a real EC or fintech app promotional banner.
Mood: {mood_desc}

--- LAYOUT ---

TOP AREA:
- Large bold Japanese headline: "{main_headline}" in red or white font, very prominent
- Smaller Japanese sub-text below: "{sub_headline}"
{event_block}

CENTER AREA:
- Main visual objects: {visual_objects}
- The smartphone (if present) shows the {featured} app interface realistically
{key_stat_block}
- Decorative accents: golden coin icons with ¥ or P symbols, sparkle stars, upward arrows

LOWER AREA:
- Supporting Japanese text summarizing the benefit clearly
- Small footer text: "{ACCOUNT_HANDLE}" in gray

--- DESIGN RULES ---
- All Japanese text must be PERFECTLY rendered and readable
- Primary color: {BRAND_COLOR_HEX} (red) for headlines and accents
- Secondary color: #FFD700 (gold/yellow) for coins and highlights
- NO CTA button
- NO photographic human faces — flat illustration style only
- Visual hierarchy: headline → key stat → supporting info → footer
- Make it look like a real Japanese SNS advertisement that stops the scroll
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
    """ユーザー写真優先、なければgpt-image-2で広告バナー生成"""
    # ① ユーザー写真を試す
    user_photo = _get_user_photo()
    if user_photo:
        try:
            image_url = _upload_to_imgbb(user_photo)
            print(f"[Image] ユーザー写真をimgbbにアップロード完了")
            return user_photo, image_url
        except Exception as e:
            print(f"[Image] imgbbアップロード失敗: {e}")
            print("[Image] gpt-image-2にフォールバック...")

    # ② gpt-image-2で広告バナー生成
    prompt = _build_infographic_prompt(caption)
    print(f"[Image] gpt-image-2で広告バナー生成中...")

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.images.generate(
        model="gpt-image-2",
        prompt=prompt,
        size="1024x1024",
        quality="medium",
        n=1,
    )

    # base64デコードして保存
    image_data = base64.b64decode(response.data[0].b64_json)
    with open(save_path, 'wb') as f:
        f.write(image_data)
    print(f"[Image] gpt-image-2 生成完了 → {save_path}")

    # imgbbにアップロード
    try:
        image_url = _upload_to_imgbb(save_path)
        print(f"[Image] imgbbアップロード完了")
    except Exception as e:
        print(f"[Image] imgbbアップロード失敗: {e}")
        image_url = None

    return save_path, image_url
