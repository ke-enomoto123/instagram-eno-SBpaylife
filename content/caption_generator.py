import random
import os
import datetime
import anthropic
from account_config import (
    ACCOUNT_PERSONA, TOPIC_CATEGORIES, HASHTAGS_JA, POST_LANGUAGE,
    LINKAGE_KNOWLEDGE, LINKAGE_TOPICS, CALENDAR_KNOWLEDGE,
)
from config import ANTHROPIC_API_KEY

POST_PATTERNS = [
    "体験談型",
    "比較型",
    "気づき型",
    "ハウツー型",
    "キャンペーン紹介型",
    "質問誘導型",
    "数字で語る型",
]

def _load_campaign_info() -> str:
    """campaigns/active.txtからキャンペーン情報を読み込む"""
    campaign_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "campaigns", "active.txt")
    if os.path.exists(campaign_file):
        with open(campaign_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                return content
    return ""


def _select_topic_with_priority() -> tuple[str, str, str]:
    """
    投稿トピックを優先度に従って選定。
    優先度: ① キャンペーン情報 ② 月初/週初のお得カレンダー ③ 連携系（40%）④ 通常 topic（60%）
    返値: (topic, mode, extra_context_block)
      mode: "campaign" / "calendar" / "linkage" / "normal"
      extra_context_block: プロンプトに追加で挿入する文字列ブロック
    """
    today = datetime.date.today()
    is_week_start = today.weekday() == 0  # 月曜
    is_month_start = today.day <= 3

    # ① キャンペーン情報があれば最優先
    campaign = _load_campaign_info()
    if campaign:
        block = f"""
【今使えるキャンペーン情報（事実のみ使用、捏造禁止）】
{campaign}

このキャンペーンを軸に、読者がすぐ使える形でシェアする内容にしてください。
"""
        return ("今使えるキャンペーン情報の紹介", "campaign", block)

    # ② 月初・週初は お得カレンダー優先
    if is_month_start:
        block = f"""
【今月のお得カレンダー（参考知識）】
{CALENDAR_KNOWLEDGE}

今月のお得日・キャンペーン日のスケジュール感を整理する投稿にしてください。
日付（5のつく日・日曜・月初・月末等）を具体的に並べて、読者が予定を組めるように。
"""
        return ("今月のお得カレンダー", "calendar", block)
    if is_week_start:
        block = f"""
【今週のお得スケジュール（参考知識）】
{CALENDAR_KNOWLEDGE}

今週どの日に何のキャンペーンがあるかをコンパクトに整理する投稿にしてください。
"""
        return ("今週のお得スケジュール", "calendar", block)

    # ③ 連携系（40%）
    if random.random() < 0.4:
        topic = random.choice(LINKAGE_TOPICS)
        block = f"""
【連携の知識（事実として参照、捏造禁止）】
{LINKAGE_KNOWLEDGE}

連携の必要性・どう得になるか・どこで連携できるか（Web URL or My Softbankアプリ手順）を
読者に分かりやすく示してください。URLやアプリの導線は知識ブロックの内容を正確に転載。
"""
        return (topic, "linkage", block)

    # ④ 通常 topic
    return (random.choice(TOPIC_CATEGORIES), "normal", "")

def _select_post_type() -> str:
    """投稿タイプを選択（時間帯別）"""
    time_of_day = os.getenv("TIME_OF_DAY", "general")
    if time_of_day == "morning":
        return random.choice(["ハウツー型", "気づき型", "数字で語る型"])
    elif time_of_day == "noon":
        return random.choice(["体験談型", "比較型", "キャンペーン紹介型"])
    else:  # evening
        return random.choice(["キャンペーン紹介型", "質問誘導型", "体験談型"])

def _generate_caption(topic: str, pattern: str, mode: str, extra_block: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # mode に応じて長さを最適化
    if mode == "linkage":
        length_type = random.choices(["medium", "long"], weights=[30, 70], k=1)[0]
    elif mode == "calendar":
        length_type = "long"
    else:
        length_type = random.choices(["short", "medium", "long"], weights=[30, 40, 30], k=1)[0]

    length_instruction = {
        "short": "30〜60文字。一言で刺すような短いキャプション",
        "medium": "80〜150文字。体験や気づきを2〜3文で",
        "long": "150〜280文字。具体的な数字や手順を含めたお得情報",
    }[length_type]

    prompt = f"""あなたは以下のペルソナでInstagramのキャプションを書いてください。

【ペルソナ】
{ACCOUNT_PERSONA}

【投稿トピック】
{topic}

【投稿パターン】
{pattern}

【文字数】
{length_instruction}
{extra_block}

【SoftBankユーザー向け基礎知識（事実のみ・必要に応じて活用）】
- LYPプレミアム：通常月額508円（税込）→ SoftBankの対象プランユーザーは無料で使える
- LYPプレミアム会員はYahoo!ショッピングでポイント還元率が毎日+2倍になる
- PayPayカードのYahoo!ショッピング利用でさらに+1倍（合計で最大5〜7%還元も可能）
- PayPayカード基本還元率：1.5%（どこで使っても）
- PayPayステップ：月の利用条件を達成すると翌月の還元率が最大+0.5%アップ
- Yahoo!ショッピングは5のつく日・日曜日にポイント倍増キャンペーンが多い
- SoftBankまとめて支払いでPayPayポイントが貯まるサービスもある

【ルール】
- 「SoftBankユーザーなら」「SoftBankユーザーだから」「SoftBankユーザーは」のニュアンスを自然に含める
- 捏造はNG。具体的な数字は上記の基礎知識か、よく知られた事実のみ使用
- 企業の宣伝っぽくならない。あくまで一ユーザーの体験・発見として書く
- 絵文字を1〜2個使う
- 最後に「。」をつけない
- ハッシュタグは含めない（別途追加する）

キャプション本文のみ出力してください。"""

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text.strip()

    # 長さ制限
    max_chars = {"short": 60, "medium": 150, "long": 250}[length_type]
    if len(text) > max_chars * 2:
        for sep in ["。", "\n"]:
            if sep in text[:max_chars + 40]:
                text = text[:text.index(sep, max_chars - 20) + 1] if sep in text[max_chars - 20:] else text
                break
        else:
            text = text[:max_chars]
    text = text.rstrip("。")

    return text

def _score_caption(caption: str, topic: str) -> float:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": f"""以下のInstagramキャプションを1〜10で採点してください。数字のみ回答。

評価基準：
- SoftBank経済圏ユーザーとして自然か
- 企業っぽくないか（NG）
- 共感・保存されそうか
- 捏造・誇張がないか

トピック：{topic}
キャプション：{caption}

点数（数字のみ）:"""
        }],
    )
    try:
        return float(message.content[0].text.strip().split()[0])
    except:
        return 7.0

def build_caption() -> dict:
    topic, mode, extra_block = _select_topic_with_priority()
    # mode によってパターンも調整
    if mode == "campaign":
        pattern = "キャンペーン紹介型"
    elif mode == "calendar":
        pattern = "ハウツー型"
    elif mode == "linkage":
        pattern = random.choice(["ハウツー型", "気づき型", "比較型"])
    else:
        pattern = _select_post_type()

    print(f"[Caption] mode={mode} / トピック: {topic}")
    print(f"[Caption] パターン: {pattern}")

    caption = _generate_caption(topic, pattern, mode, extra_block)
    score = _score_caption(caption, topic)
    print(f"[Caption] 品質スコア: {score}/10.0")

    max_retries = 2
    for i in range(max_retries):
        if score >= 7.0:
            break
        print(f"[Caption] スコア不足 → 再生成 ({i+1}/{max_retries})")
        caption = _generate_caption(topic, pattern, mode, extra_block)
        score = _score_caption(caption, topic)
        print(f"[Caption] 品質スコア: {score}/10.0")

    # ハッシュタグ選択（5〜8個）
    selected_hashtags = random.sample(HASHTAGS_JA, min(7, len(HASHTAGS_JA)))
    hashtag_text = " ".join(selected_hashtags)

    full_caption = f"{caption}\n\n{hashtag_text}"

    return {
        "caption": full_caption,
        "score": score,
        "topic": topic,
        "pattern": pattern,
        "mode": mode,
    }
