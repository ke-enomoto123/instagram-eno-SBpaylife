import os
import json
import random
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

# 画像スタイル（ランダム選択）
IMAGE_STYLES = ["ad_banner", "awareness_infographic"]


def _analyze_caption(caption: str) -> dict:
    """Claudeでキャプションを広告コンセプトに分析（正確な事実知識付き）"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": f"""以下のInstagram投稿テキストを読んで、画像コンセプトをJSONで出力してください。

投稿テキスト:
{caption}

【⚠️ 正確な事実知識（2026年5月時点公式情報・捏造禁止）】

Yahoo!ショッピングの還元率は「上乗せ」構造:
- 毎日5%（内訳: ストア1% + 指定決済0.5〜1.0% + LINE連携由来3〜4%）
- LYPプレミアム会員 +2%（毎日、上限5,000円相当/月）
- 5のつく日 +4%（上限1,000円相当/開催）
- LYP会員の日曜+5%（要エントリー・5,000円以上・対象ストアのみ・上限2,000円相当/開催期間）

合計例:
- 通常日 LYP+LINE連携で最大7%
- 5のつく日 LYP+LINE連携で最大11%
- 日曜 LYP+LINE連携で最大12%
※「+5%」は既存還元への上乗せ。「通常1%→日曜6%」のような単独比較は誤り

LYPプレミアム:
- Web版月額508円、iOS/Androidアプリ版650円
- SoftBank対象プラン+個人契約+スマートログインで Web版が無料

【⚠️ 連携の正しい構造】
中央に「Yahoo! JAPAN ID」、そこから3つのサービスが個別に繋がる:
- スマートログイン: SoftBank（携帯番号） ↔ Yahoo! JAPAN ID
- PayPay連携: PayPay ↔ Yahoo! JAPAN ID
- LINE連携: LINE ↔ Yahoo! JAPAN ID
※「My SoftBank ↔ PayPay 直接連携」のような図は誤り
※「My SoftBank」は SoftBank連携の入口（操作画面）であってサービス本体ではない

【⚠️ ビジュアル指定の注意】
- PayPayポイントを表示するロゴ/アイコンは PayPay（赤い丸に白P）のみ
- Tポイント（黄色のT）は別ブランド。絶対使わない・登場させない

出力形式（JSONのみ。説明不要）:
{{
  "main_headline": "最も目立たせるメインコピー（15文字以内）",
  "sub_headline": "サブコピー（25文字以内）",
  "key_stat": "強調したい数字・特典（事実のみ。例: 月額0円、最大12%還元、+5%上乗せ）",
  "featured_service": "メインのサービス名（例: Yahoo!ショッピング, PayPay, LYPプレミアム）",
  "event_trigger": "日付・イベント名があれば（例: 5のつく日、日曜）",
  "visual_objects": "画像内オブジェクト（英語）。PayPayの場合は 'PayPay app icon (red circle with white P)' と明記、Tポイント等他ブランドアイコンは絶対使わない",
  "awareness_hook": "気づかせる一言（事実ベース）",
  "compare_before": "知らない人の状態（事実のみ）",
  "compare_after": "知った後の状態（事実のみ）",
  "mood": "雰囲気（excited/warm/premium のどれか）"
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


def _prompt_ad_banner(c: dict) -> str:
    """広告バナー型プロンプト"""
    main_headline  = c.get("main_headline", "知らないと損！")
    sub_headline   = c.get("sub_headline", "SoftBankユーザー限定のお得情報")
    key_stat       = c.get("key_stat", "")
    featured       = c.get("featured_service", "Yahoo!ショッピング")
    event_trigger  = c.get("event_trigger", "")
    visual_objects = c.get("visual_objects", "smartphone showing shopping app, golden coins, red shopping bag")
    mood           = c.get("mood", "excited")

    event_block    = f'- TOP-RIGHT CORNER: Calendar or badge icon with Japanese text: "{event_trigger}"' if event_trigger else ""
    key_stat_block = f'- Large starburst badge with Japanese text "{key_stat}" in huge bold font' if key_stat else ""

    mood_desc = {
        "excited": "bright and energetic — red/yellow dominant, white background with sunburst lines",
        "warm":    "warm and friendly — orange/yellow palette, soft gradient",
        "premium": "sophisticated — dark navy background with gold accents",
    }.get(mood, "bright and energetic — red/yellow dominant, white background with sunburst lines")

    return f"""
Create a high-quality Japanese promotional banner (1:1 square, 1024x1024px) for Instagram.
Style: professional Japanese SNS advertisement — like a real EC or fintech app promotional graphic.
Mood: {mood_desc}

LAYOUT:
- TOP: Large bold Japanese headline "{main_headline}" in red font. Below: sub-text "{sub_headline}"
{event_block}
- CENTER: Main visuals — {visual_objects}. The smartphone shows {featured} app realistically.
{key_stat_block}
  Golden coin icons (¥/P symbols), sparkle stars, upward arrows as decorative accents.
- BOTTOM: Supporting Japanese benefit text. Footer: "{ACCOUNT_HANDLE}" in small gray.

RULES:
- All Japanese text perfectly rendered and readable
- Primary: {BRAND_COLOR_HEX} red. Secondary: #FFD700 gold/yellow
- NO CTA button. NO photographic faces — flat illustration style
- Scroll-stopping visual impact

⚠️ CRITICAL ACCURACY RULES:
- For PayPay points/wallet visuals: use PayPay logo (red circle with white "P"), NEVER use Tポイント (yellow T) or any other point service brand mark
- "利用可能ポイント" / "PayPayポイント" displays must show PayPay branding only
- For SoftBank/Yahoo/PayPay/LINE 連携 (linkage) diagrams: the CENTRAL HUB is "Yahoo! JAPAN ID", with three separate connections: (1) SoftBank ↔ Yahoo! JAPAN ID via Smart Login, (2) PayPay ↔ Yahoo! JAPAN ID, (3) LINE ↔ Yahoo! JAPAN ID. NEVER draw a direct "My SoftBank ↔ PayPay" connection — My SoftBank is just the entry point UI for SoftBank linkage, not a service node.
- All numbers/percentages shown must match the factual knowledge given (Yahoo!ショッピング is "+5%上乗せ" structure, not "1%→6%" misleading single-rate comparison)
"""


def _prompt_awareness_infographic(c: dict) -> str:
    """自ら気づき系インフォグラフィック型プロンプト"""
    main_headline  = c.get("main_headline", "知ってた？")
    awareness_hook = c.get("awareness_hook", "SoftBankユーザーには隠れた特典がある")
    key_stat       = c.get("key_stat", "")
    compare_before = c.get("compare_before", "知らずに損している状態")
    compare_after  = c.get("compare_after", "知った後にお得になった状態")
    featured       = c.get("featured_service", "LYPプレミアム")
    mood           = c.get("mood", "warm")

    key_stat_block = f'- A large highlighted circle or badge showing "{key_stat}" as the KEY DISCOVERY number' if key_stat else ""

    mood_desc = {
        "excited": "clean white background with light blue and yellow accents — feels like a helpful tips article",
        "warm":    "warm cream or light orange background — feels like a friendly magazine spread",
        "premium": "light gray background with clean lines — feels like a quality financial guide",
    }.get(mood, "clean white background with light blue and yellow accents — feels like a helpful tips article")

    return f"""
Create a Japanese "did you know?" awareness infographic (1:1 square, 1024x1024px) for Instagram.
Style: educational and eye-opening — like a helpful tips post from a Japanese lifestyle magazine or SNS influencer.
Mood: {mood_desc}

LAYOUT:

TOP SECTION:
- A thought bubble or lightbulb icon
- Bold Japanese question or hook text: "{main_headline}"
- Below: "{awareness_hook}" — written as a surprising discovery

MIDDLE SECTION (BEFORE vs AFTER comparison):
- LEFT column labeled "知らないと…" with a downward arrow icon
  Content: "{compare_before}" — illustrated with a sad or confused icon/emoji
- RIGHT column labeled "知ってると！" with an upward arrow icon
  Content: "{compare_after}" — illustrated with a happy or celebratory icon/emoji
- Dividing line or VS badge between the two columns
{key_stat_block}

BOTTOM SECTION:
- Summary tip text in Japanese: this is the key insight about {featured}
- Footer: "{ACCOUNT_HANDLE}" in small gray text

DESIGN RULES:
- Clean, minimal, easy-to-read layout — NOT a busy advertisement
- Uses icons and simple illustrations, NOT photographic images
- Primary accent: {BRAND_COLOR_HEX} red for key numbers and highlights
- Gold/yellow (#FFD700) for positive "after" elements
- Gray or light blue for negative "before" elements
- Japanese text must be perfectly rendered
- Feels like a discovery — the reader should think "え、知らなかった！"

⚠️ CRITICAL ACCURACY RULES:
- For PayPay points/wallet visuals: use PayPay logo (red circle with white "P"), NEVER use Tポイント (yellow T) or any other point service brand mark
- For SoftBank/Yahoo/PayPay/LINE 連携 (linkage) diagrams: the CENTRAL HUB is "Yahoo! JAPAN ID", with three connections branching out: (1) SoftBank/My SoftBank ↔ Yahoo! JAPAN ID (via Smart Login), (2) PayPay ↔ Yahoo! JAPAN ID, (3) LINE ↔ Yahoo! JAPAN ID. NEVER draw a direct "My SoftBank ↔ PayPay" connection.
- All numbers shown must match factual knowledge (e.g., LYP+5% is on top of existing 7%, not a single 5% delta from 1%)
"""


def _build_prompt(caption: str) -> str:
    """キャプション分析 → ランダムにスタイル選択してプロンプト生成"""
    try:
        c = _analyze_caption(caption)
        print(f"[Image] 広告コンセプト: {c}")
    except Exception as e:
        print(f"[Image] キャプション分析失敗、デフォルト使用: {e}")
        c = {}

    style = random.choice(IMAGE_STYLES)
    print(f"[Image] スタイル: {style}")

    if style == "ad_banner":
        return _prompt_ad_banner(c)
    else:
        return _prompt_awareness_infographic(c)


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


def _generate_with_openai(prompt: str, save_path: str) -> str | None:
    """gpt-image-2 → gpt-image-1 の順でフォールバックして生成。imgbb URLを返す"""
    client = OpenAI(api_key=OPENAI_API_KEY)

    for model in ["gpt-image-2", "gpt-image-1"]:
        try:
            print(f"[Image] {model} で画像生成中...")
            response = client.images.generate(
                model=model,
                prompt=prompt,
                size="1024x1024",
                quality="medium",
                n=1,
            )
            image_data = base64.b64decode(response.data[0].b64_json)
            with open(save_path, 'wb') as f:
                f.write(image_data)
            print(f"[Image] {model} 生成完了 → {save_path}")

            try:
                image_url = _upload_to_imgbb(save_path)
                print(f"[Image] imgbbアップロード完了")
                return image_url
            except Exception as e:
                print(f"[Image] imgbbアップロード失敗: {e}")
                return None

        except Exception as e:
            print(f"[Image] {model} 失敗: {e}")
            if model == "gpt-image-1":
                raise  # 両方失敗したら例外を上げる
            print(f"[Image] {model} → gpt-image-1 にフォールバック...")

    return None


def generate_image(caption: str, save_path: str):
    """ユーザー写真優先、なければgpt-image-2（→gpt-image-1フォールバック）で生成"""
    # ① ユーザー写真を試す
    user_photo = _get_user_photo()
    if user_photo:
        try:
            image_url = _upload_to_imgbb(user_photo)
            print(f"[Image] ユーザー写真をimgbbにアップロード完了")
            return user_photo, image_url
        except Exception as e:
            print(f"[Image] imgbbアップロード失敗: {e}")

    # ② OpenAI画像生成（gpt-image-2 → gpt-image-1 フォールバック）
    prompt = _build_prompt(caption)
    image_url = _generate_with_openai(prompt, save_path)

    return save_path, image_url
