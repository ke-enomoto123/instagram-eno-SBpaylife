"""
carousel_generator.py
カルーセル投稿用のスライド生成:
- 構成: Claude Haiku がキャプションからカルーセル構成JSONを生成
- 表紙: 既存の image_generator (gpt-image-2) の画像をそのまま使用
- 中身/まとめ/CTA: PIL でテキストスライドを描画（コスト増なし）

スライド数は「5枚」または「8〜10枚」に振り分ける
（4〜7枚は完読率が最も落ちるU字カーブの谷のため避ける）
"""
from __future__ import annotations
import os
import json
import random
import anthropic
from PIL import Image, ImageDraw, ImageFont
from config import ANTHROPIC_API_KEY

CANVAS = 1080

# ブランドカラー（お得系: 白地×赤×ゴールド）
BG_COLOR = "#FFF9F2"          # 温かみのある白
ACCENT = "#E8412C"            # 赤（見出し・番号）
TEXT_DARK = "#2B2B2B"         # 本文
TEXT_GRAY = "#8A8A8A"         # 補足・フッター
GOLD = "#C8A45D"              # 区切り線
CTA_BG = "#E8412C"            # CTAスライドの背景
CTA_TEXT = "#FFFFFF"

FONT_CANDIDATES_BOLD = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]
FONT_CANDIDATES_REGULAR = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]


def _find_font(candidates: list) -> str | None:
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = _find_font(FONT_CANDIDATES_BOLD if bold else FONT_CANDIDATES_REGULAR)
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
    """日本語対応の文字単位折り返し"""
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for ch in paragraph:
            test = line + ch
            if font.getbbox(test)[2] > max_width and line:
                lines.append(line)
                line = ch
            else:
                line = test
        lines.append(line)
    return lines


def build_carousel_structure(caption: str, topic: str) -> dict | None:
    """Claude Haiku でカルーセル構成JSONを生成"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # 5枚（本編2枚）or 9-10枚（本編5-6枚）に振り分け。4-7枚の谷を避ける
    long_format = random.random() < 0.5
    n_slides = "5〜6個" if long_format else "2個"

    prompt = f"""以下のInstagram投稿キャプションを、保存されやすい「カルーセル投稿」の構成に分解してください。

キャプション:
{caption}

トピック: {topic}

【カルーセルの設計思想】
- 表紙は「数字入り10〜15字のフック」（例:「月5,000円損してる人の特徴」「知らないと損する3つの設定」）
- 中身スライドは1枚1メッセージ。読者が「なるほど」と思う具体情報
- 数字は「期間×金額×割合」で具体的に（例: 月5,000円 / 20%還元 / 9割が知らない）
- 損失回避の言葉が刺さる（「知らないと損」「やらないだけで差がつく」）
- 手順は3ステップに圧縮
- 事実は正確に。キャプションにない事実の捏造はNG

出力形式（JSONのみ。説明不要）:
{{
  "cover_title": "表紙の大きなフックタイトル（10〜15字、数字入り推奨）",
  "cover_subtitle": "表紙のサブタイトル（15〜25字）",
  "slides": [
    {{"heading": "スライド見出し（15字以内）", "body": "本文（60〜90字。具体的な情報・数字・手順）"}}
  ],
  "summary_points": ["まとめの箇条書き1（20字以内）", "まとめ2", "まとめ3"],
  "cta_text": "保存を促す一言（20〜30字。理由付き。例: 週末の買い物前に見返せるように保存してね）"
}}

slides は{n_slides}作ってください。"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        if "```" in text:
            for part in text.split("```"):
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                try:
                    return json.loads(part)
                except Exception:
                    continue
        return json.loads(text)
    except Exception as e:
        print(f"[Carousel] 構成生成失敗: {e}")
        return None


def _draw_footer(draw: ImageDraw.ImageDraw, page: int, total: int, handle: str):
    """ページドット＋ハンドルのフッター"""
    font_small = _font(28)
    # ドット
    dot_r = 6
    gap = 26
    total_w = (total - 1) * gap
    start_x = CANVAS // 2 - total_w // 2
    y = CANVAS - 90
    for i in range(total):
        color = ACCENT if i == page else "#D9CFC4"
        x = start_x + i * gap
        draw.ellipse([x - dot_r, y - dot_r, x + dot_r, y + dot_r], fill=color)
    # ハンドル
    draw.text((CANVAS // 2, CANVAS - 46), handle, font=font_small, fill=TEXT_GRAY, anchor="mm")


def render_content_slide(heading: str, body: str, number: int, page: int, total: int,
                          handle: str, save_path: str) -> str:
    """本編スライド: 番号＋見出し＋本文"""
    img = Image.new("RGB", (CANVAS, CANVAS), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 上部の番号バッジ
    font_num = _font(72, bold=True)
    badge_r = 68
    cx, cy = CANVAS // 2, 190
    draw.ellipse([cx - badge_r, cy - badge_r, cx + badge_r, cy + badge_r],
                 outline=ACCENT, width=5)
    draw.text((cx, cy), str(number), font=font_num, fill=ACCENT, anchor="mm")

    # 見出し
    font_head = _font(64, bold=True)
    head_lines = _wrap(heading, font_head, CANVAS - 160)
    y = 340
    for line in head_lines:
        draw.text((CANVAS // 2, y), line, font=font_head, fill=TEXT_DARK, anchor="mm")
        y += 84

    # 区切り線
    y += 20
    draw.line([(CANVAS // 2 - 60, y), (CANVAS // 2 + 60, y)], fill=GOLD, width=4)
    y += 60

    # 本文
    font_body = _font(44)
    body_lines = _wrap(body, font_body, CANVAS - 200)
    for line in body_lines:
        draw.text((CANVAS // 2, y), line, font=font_body, fill=TEXT_DARK, anchor="mm")
        y += 66

    _draw_footer(draw, page, total, handle)
    img.save(save_path, "JPEG", quality=92)
    return save_path


def render_summary_slide(points: list, page: int, total: int, handle: str, save_path: str) -> str:
    """まとめスライド: チェックリスト形式"""
    img = Image.new("RGB", (CANVAS, CANVAS), BG_COLOR)
    draw = ImageDraw.Draw(img)

    font_title = _font(72, bold=True)
    draw.text((CANVAS // 2, 170), "まとめ", font=font_title, fill=ACCENT, anchor="mm")
    draw.line([(CANVAS // 2 - 70, 240), (CANVAS // 2 + 70, 240)], fill=GOLD, width=4)

    font_body = _font(48, bold=True)
    y = 380
    for pt in points[:4]:
        # チェックマーク
        draw.text((140, y), "✓", font=_font(52, bold=True), fill=ACCENT, anchor="lm")
        for line in _wrap(pt, font_body, CANVAS - 340):
            draw.text((220, y), line, font=font_body, fill=TEXT_DARK, anchor="lm")
            y += 72
        y += 50

    _draw_footer(draw, page, total, handle)
    img.save(save_path, "JPEG", quality=92)
    return save_path


def render_cta_slide(cta_text: str, page: int, total: int, handle: str, save_path: str) -> str:
    """CTAスライド: 保存・シェア誘導（赤背景）"""
    img = Image.new("RGB", (CANVAS, CANVAS), CTA_BG)
    draw = ImageDraw.Draw(img)

    # 保存アイコン風のブックマーク
    bx, by, bw, bh = CANVAS // 2 - 50, 170, 100, 130
    draw.polygon([(bx, by), (bx + bw, by), (bx + bw, by + bh),
                  (bx + bw // 2, by + bh - 36), (bx, by + bh)], fill="#FFFFFF")

    font_main = _font(58, bold=True)
    y = 430
    for line in _wrap(cta_text, font_main, CANVAS - 220):
        draw.text((CANVAS // 2, y), line, font=font_main, fill=CTA_TEXT, anchor="mm")
        y += 84

    y += 40
    font_sub = _font(38)
    for line in _wrap("お得な情報を見逃したくない人は\nフォローもどうぞ", font_sub, CANVAS - 260):
        draw.text((CANVAS // 2, y), line, font=font_sub, fill="#FFE3DC", anchor="mm")
        y += 56

    # フッター（CTA面は白ドット）
    font_small = _font(28)
    draw.text((CANVAS // 2, CANVAS - 46), handle, font=font_small, fill="#FFD1C7", anchor="mm")
    img.save(save_path, "JPEG", quality=92)
    return save_path


def build_carousel_slides(caption: str, topic: str, cover_path: str, handle: str,
                          out_dir: str = "/tmp") -> tuple[list, dict] | tuple[None, None]:
    """
    カルーセル全スライドを生成。
    返値: (ローカル画像パスのリスト [表紙, 本編..., まとめ, CTA], 構成dict)
    失敗時: (None, None) → 呼び出し側で単発画像にフォールバック
    """
    structure = build_carousel_structure(caption, topic)
    if not structure or not structure.get("slides"):
        return None, None

    slides_meta = structure["slides"]
    total = 1 + len(slides_meta) + (1 if structure.get("summary_points") else 0) + 1

    # Instagram APIのカルーセル上限は10枚
    if total > 10:
        slides_meta = slides_meta[: 10 - 3]
        total = 1 + len(slides_meta) + 1 + 1

    paths = [cover_path]
    page = 1

    for i, s in enumerate(slides_meta, start=1):
        p = os.path.join(out_dir, f"carousel_slide_{i}.jpg")
        render_content_slide(
            heading=s.get("heading", ""), body=s.get("body", ""),
            number=i, page=page, total=total, handle=handle, save_path=p,
        )
        paths.append(p)
        page += 1

    if structure.get("summary_points"):
        p = os.path.join(out_dir, "carousel_summary.jpg")
        render_summary_slide(structure["summary_points"], page, total, handle, p)
        paths.append(p)
        page += 1

    p = os.path.join(out_dir, "carousel_cta.jpg")
    render_cta_slide(
        structure.get("cta_text", "あとで見返せるように保存してね"),
        page, total, handle, p,
    )
    paths.append(p)

    print(f"[Carousel] {len(paths)}枚のスライド生成完了")
    return paths, structure
