import io
import os

from PIL import Image

GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY")


def generate_infographic(news: dict, save_path: str = "/tmp/infographic.png") -> str:
    """
    Gemini 2.0 Flash でニュース内容をインフォグラフィック画像に変換。
    Returns: 保存したファイルパス
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise ImportError("google-genai が未インストールです: pip install google-genai")

    client = genai.Client(api_key=GOOGLE_AI_API_KEY)

    prompt = f"""Create a clean, modern Japanese infographic image for social media (X/Twitter post, portrait orientation).

Topic category: {news['category']}
News headline: {news['title']}
Details: {news['summary']}

Design requirements:
- Portrait orientation (9:16 ratio ideal for mobile)
- Background: clean white or very light gray
- Accent colors: PayPay red (#FF0033) and SoftBank light blue (#0095D9)
- Large bold Japanese headline at the top (use the news title)
- Visual flow diagram in the center: show the benefit mechanism with icons and arrows
  Example flow: SoftBankユーザー → PayPay払い → ポイント還元 → お得！
- 3 to 5 key benefit points as bullet items with checkmark icons
- "SoftBankユーザー限定" badge or label (red or blue, rounded rectangle)
- Clean sans-serif typography, all text in Japanese
- Bottom area: small note about the source or date if available
- Professional but friendly and easy to understand at a glance

Do NOT use placeholder text. Use the actual Japanese content from the news provided above.
Generate a complete, ready-to-post infographic image."""

    print(f"[Infographic] Gemini APIで画像生成中...")

    response = client.models.generate_content(
        model="gemini-2.0-flash-preview-image-generation",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"]
        ),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            image_bytes = part.inline_data.data
            image = Image.open(io.BytesIO(image_bytes))
            os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else ".", exist_ok=True)
            image.save(save_path)
            print(f"[Infographic] 生成完了: {save_path} ({image.size[0]}x{image.size[1]}px)")
            return save_path

    raise RuntimeError("[Infographic] Gemini APIから画像が返されませんでした")
