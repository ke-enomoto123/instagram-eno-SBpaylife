import io
import os

import requests
from openai import OpenAI
from PIL import Image

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def generate_infographic(news: dict, save_path: str = "/tmp/infographic.png") -> str:
    """
    DALL-E 3 でニュース内容をインフォグラフィック画像に変換。
    Returns: 保存したファイルパス
    """
    client = OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""Clean, modern Japanese infographic image for social media (X/Twitter post).

Topic: {news['category']}
Headline: {news['title']}
Details: {news['summary'][:300]}

Design:
- Portrait orientation, white background
- PayPay red (#FF0033) and SoftBank light blue (#0095D9) as accent colors
- Large bold Japanese headline at top
- Center: simple flow diagram with icons and arrows showing the benefit (e.g. SoftBankユーザー → PayPay払い → ポイント還元 → お得！)
- 3-5 key points as bullet items with checkmarks
- Red or blue rounded badge: "SoftBankユーザー限定"
- Clean sans-serif Japanese typography
- Professional, easy to read at a glance
- NO placeholder text, use the actual Japanese content above"""

    print(f"[Infographic] DALL-E 3で画像生成中...")

    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1792",
        quality="standard",
        n=1,
    )

    image_url = response.data[0].url
    print(f"[Infographic] 生成完了。ダウンロード中...")

    img_data = requests.get(image_url, timeout=30).content
    os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else ".", exist_ok=True)
    with open(save_path, "wb") as f:
        f.write(img_data)

    image = Image.open(save_path)
    print(f"[Infographic] 保存完了: {save_path} ({image.size[0]}x{image.size[1]}px)")
    return save_path
