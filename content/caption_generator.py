import random
import os
import datetime
import anthropic
from account_config import (
    ACCOUNT_PERSONA, TOPIC_CATEGORIES, HASHTAGS_JA, POST_LANGUAGE,
    LINKAGE_KNOWLEDGE, LINKAGE_TOPICS, CALENDAR_KNOWLEDGE,
)
from config import ANTHROPIC_API_KEY

# お得系の「バズる型」（2026年SNS調査ベース）
POST_PATTERNS = [
    "数字リスト型（「◯選」まとめ。今月のお得を箇条書きで網羅）",
    "損失回避型（「知らないと損してる」。やってない人が失っている金額を可視化）",
    "締切型（【今日まで】【残り3日】を冒頭に。締切リマインド）",
    "実績ビフォーアフター型（「今月+◯◯円」。期間×金額の実績から手順を逆算）",
    "3ステップ手順型（「①DL ②クーポン ③使うだけ」。5分でできる感）",
    "比較型（「何もしない場合 vs 設定した場合」の差額提示）",
    "質問誘導型（意見が割れる問いでコメント欄を活性化）",
]

# 型ごとの選択重み（損失回避・数字リストを厚めに）
POST_PATTERN_WEIGHTS = [25, 25, 10, 15, 10, 10, 5]

# 保存・シェアを促すCTA（IGの拡散はsends/保存が最重要シグナル）
IG_CTA_OPTIONS = [
    "買い物の前に見返せるように保存してね",
    "あとで設定する時のために保存しておくと便利だよ",
    "SoftBankユーザーの友達がいたら送ってあげて",
    "気になったやつの番号、コメントで教えて",
    "他にも知りたいお得があったらコメントで教えてね",
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


def _select_topic_with_priority(forced_topic: str = None) -> tuple[str, str, str]:
    """
    投稿トピックを優先度に従って選定。
    forced_topic が指定された場合は優先度を無視してそのトピックを使用（ニュース連動など）。
    優先度: ① キャンペーン情報 ② 月初/週初のお得カレンダー ③ 連携系（40%）④ 通常 topic（60%）
    返値: (topic, mode, extra_context_block)
      mode: "forced" / "campaign" / "calendar" / "linkage" / "normal"
      extra_context_block: プロンプトに追加で挿入する文字列ブロック
    """
    if forced_topic:
        # forced_topicでもキャンペーン情報があれば併載
        campaign = _load_campaign_info()
        block = ""
        if campaign:
            block = f"""
【今使えるキャンペーン情報（事実のみ使用、捏造禁止）】
{campaign}

このキャンペーン情報も自然に絡めてください。
"""
        return (forced_topic, "forced", block)

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
    """投稿タイプを重み付き選択（損失回避・数字リストを優先）"""
    return random.choices(POST_PATTERNS, weights=POST_PATTERN_WEIGHTS, k=1)[0]

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

【バズる書き方の鉄則（2026年SNS調査ベース）】
- 1行目は10〜15字のフックで始める（例:「知らないと月5,000円損」「9割がやってない設定」）
- 数字は「期間×金額×割合」の3点セットで具体化（曖昧な「お得」は使わない）
- 損失回避で書く:「◯◯% お得」より「◯◯円 損してる」の方が刺さる
- 手順を書くときは3ステップに圧縮（①②③）
- 検索キーワード（PayPay、Yahoo!ショッピング、LYPプレミアム等のサービス名）を本文に自然に含める

【ルール】
- 「SoftBankユーザーなら」「SoftBankユーザーだから」「SoftBankユーザーは」のニュアンスを自然に含める
- 捏造はNG。具体的な数字は上記の基礎知識か、よく知られた事実のみ使用
- 企業の宣伝っぽくならない。あくまで一ユーザーの体験・発見として書く
- 絵文字を1〜2個使う
- 最後に「。」をつけない
- ハッシュタグは含めない（別途追加する）
- CTAは含めない（別途追加する）

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

def build_caption(forced_topic: str = None) -> dict:
    topic, mode, extra_block = _select_topic_with_priority(forced_topic=forced_topic)
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

    # CTA（保存・DMシェア誘導。IGの拡散はsends/保存が最重要シグナル）
    cta = random.choice(IG_CTA_OPTIONS)

    # ハッシュタグは4個に絞る（現在のIGはハッシュタグよりキーワードキャプション重視）
    selected_hashtags = random.sample(HASHTAGS_JA, min(4, len(HASHTAGS_JA)))
    hashtag_text = " ".join(selected_hashtags)

    full_caption = f"{caption}\n\n{cta}\n\n{hashtag_text}"

    return {
        "caption": full_caption,
        "score": score,
        "topic": topic,
        "pattern": pattern,
        "mode": mode,
    }


def build_x_caption(forced_topic: str = None) -> dict:
    """X (Twitter) 専用：短くシンプルな投稿を生成（IG とは別文・100〜160文字）"""
    topic, mode, extra_block = _select_topic_with_priority(forced_topic=forced_topic)
    print(f"[X Caption] mode={mode} / トピック: {topic}")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""あなたは以下のペルソナでX（Twitter）の投稿を書いてください。

【ペルソナ】
{ACCOUNT_PERSONA}

【投稿トピック】
{topic}
{extra_block}

【⚠️ X の文字数仕様（厳守）】
- X は日本語1文字を「重み2」、英数字を「重み1」でカウントし、合計280まで
- 日本語のみだと **実質135字が上限**、余裕を見て120字
- 本文は **日本語100〜120字** を厳守
- 超えるとエラー（403 Forbidden）になる

【バズる書き方の鉄則（2026年Xアルゴリズム調査ベース）】
- 1行目の最初の10文字で「誰得か」を宣言（例:「SoftBankの人だけ得する話」「これ知らない人、損してる」）
- 損失回避のフックが最強:「知らないと損」「やらないだけで差がつく」
- 数字は「期間×金額×割合」で具体的に
- 最後は問いかけか共感で締めて、リプライを誘う（リプ往復がXの最重要シグナル）

【ルール】
- 短くてリズムよく、2〜3段落・各1〜2文
- 絵文字は1〜2個のみ
- ⚠️ ハッシュタグは絶対に入れない（Xではランキングに寄与せず、広告臭が出てマイナス）
- 「。」は付けない
- 捏造NG。具体的な数字は基礎知識か事実のみ使用
- SoftBankユーザー歴とサービスの歴史を混同しない（LYPプレミアムは2023年開始）
- 切れて『…』で終わるのは絶対NG。最初から120字に収まる完結した文を書く

本文のみ出力。"""

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    caption = message.content[0].text.strip().rstrip("。").rstrip("．")

    # 重み超過時は文末記号で安全切り
    if _tweet_weight(caption) > 270:
        caption = _truncate_for_x(caption, max_weight=270)
        print(f"[X Caption] 重み超過 → truncate")

    print(f"[X Caption] 文字数: {len(caption)} 重み: {_tweet_weight(caption)}/280")

    return {
        "caption": caption,
        "score": 7.0,
        "topic": topic,
        "pattern": "X専用",
        "mode": mode,
    }


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
    import re
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
