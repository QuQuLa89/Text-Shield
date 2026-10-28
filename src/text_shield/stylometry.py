"""標準ライブラリだけで文体特徴量とコサイン類似度を計算します。"""

import math
import re
import unicodedata
from collections import Counter
from typing import Any

from .utils import frontmatter_end
from .watermark import strip_watermarks


def extract_clean_text(markdown_text: str) -> str:
    """透かしと主要なMarkdown記法を除き、本文を返します。"""
    text = strip_watermarks(markdown_text).removeprefix("\ufeff")
    try:
        text = text[frontmatter_end(text) :]
    except ValueError:
        # 終端のない先頭の水平線は、従来どおりMarkdownとして扱います。
        pass
    text = re.sub(r"(?m)^ {0,3}\[[^\]]+\]:.*$", "", text)
    text = re.sub(
        r"(?m)^[ \t]*(?:(?:-[ \t]*){3,}|(?:\*[ \t]*){3,}|(?:_[ \t]*){3,})\r?$", "", text
    )
    # 引用や入れ子のリストの中のコードフェンスも認識します。
    text = re.sub(
        r"(?m)^[ \t]*(?:(?:>[ \t]?|[-+*][ \t]+|\d+[.)][ \t]+)[ \t]*)+", "", text
    )
    lines = []
    fence_char = ""
    fence_length = 0
    for line in text.splitlines(keepends=True):
        if fence_char:
            if re.fullmatch(
                rf"[ \t]*{re.escape(fence_char)}{{{fence_length},}}[ \t]*", line.strip()
            ):
                fence_char = ""
            # 前後の本文が一つの文としてつながらないよう改行を残します。
            lines.append("\n")
            continue
        fence = re.match(r"^[ \t]*(`{3,}|~{3,})", line)
        if fence:
            fence_char = fence[1][0]
            fence_length = len(fence[1])
            lines.append("\n")
        else:
            lines.append(line)
    text = "".join(lines)
    text = re.sub(r"(?<!`)(`+)(?!`)[\s\S]*?(?<!`)\1(?!`)", "", text)
    # URL内の括弧を1段まで扱い、リンクの表示テキストだけを残します。
    destination = r"\((?:[^()\n]|\([^()\n]*\))*\)"
    text = re.sub(r"!\[[^\]\n]*\]" + destination, "", text)
    text = re.sub(r"\[([^\]\n]*)\]" + destination, r"\1", text)
    text = re.sub(r"(?m)^[ \t]*#{1,6}(?:[ \t]+|$)", "", text)
    text = re.sub(
        r"(?m)^[ \t]*(?:(?:-[ \t]*){3,}|(?:\*[ \t]*){3,}|(?:_[ \t]*){3,})\r?$", "", text
    )
    text = re.sub(r"<!--[\s\S]*?-->|<[^>]*>", "", text)
    return text.strip()


def extract_features(text: str) -> dict[str, Any]:
    """空白以外を文字数に数え、有効文の末尾最大3文字を集計します。"""
    compact = re.sub(r"\s+", "", text)
    total_chars = len(compact)
    sentences = [
        sentence
        for part in re.split(r"[。！？\n\r]+", text)
        if len(sentence := re.sub(r"\s+", "", part)) >= 4
    ]
    endings: Counter[str] = Counter()
    for sentence in sentences:
        end = len(sentence)
        while end and unicodedata.category(sentence[end - 1]).startswith("P"):
            end -= 1
        if end >= 2:
            endings[sentence[:end][-3:]] += 1

    def ratio(pattern: str) -> float:
        return len(re.findall(pattern, compact)) / total_chars if total_chars else 0.0

    return {
        "total_chars": total_chars,
        "kanji_ratio": ratio(r"[\u4e00-\u9fff]"),
        "hiragana_ratio": ratio(r"[\u3040-\u309f]"),
        "katakana_ratio": ratio(r"[\u30a0-\u30ff]"),
        "latin_ratio": ratio(r"[a-zA-Z0-9]"),
        "total_sentences": len(sentences),
        "avg_sentence_len": (
            sum(map(len, sentences)) / len(sentences) if sentences else 0.0
        ),
        "comma_ratio": ratio(r"[、,]"),
        "exclamation_ratio": ratio(r"[！？!?]"),
        "ending_counts": dict(endings),
        "top_endings": endings.most_common(5),
    }


def build_feature_vector(
    features: dict[str, Any], vocabulary: list[str]
) -> list[float]:
    """数値特徴量7個と、共通語彙順の文末頻度比率を返します。"""
    vector = [
        features["kanji_ratio"],
        features["hiragana_ratio"],
        features["katakana_ratio"],
        features["latin_ratio"],
        min(features["avg_sentence_len"] / 100.0, 1.0),
        min(features["comma_ratio"] * 10.0, 1.0),
        min(features["exclamation_ratio"] * 20.0, 1.0),
    ]
    total = features["total_sentences"]
    vector.extend(
        features["ending_counts"].get(ending, 0) / total if total else 0.0
        for ending in vocabulary
    )
    return vector


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """同じ次元のベクトルを比較し、0.0〜1.0に収めた類似度を返します。"""
    if len(vec1) != len(vec2):
        raise ValueError("特徴ベクトルの次元数が一致していません。")
    norm1, norm2 = math.hypot(*vec1), math.hypot(*vec2)
    if not norm1 or not norm2:
        return 1.0 if norm1 == norm2 else 0.0
    similarity = math.fsum(
        (a / norm1) * (b / norm2) for a, b in zip(vec1, vec2, strict=True)
    )
    return max(0.0, min(similarity, 1.0))


def compare_texts(source_text: str, target_text: str) -> dict[str, Any]:
    """本文を抽出して比較し、特徴量・類似度・評価を返します。"""
    source = extract_features(extract_clean_text(source_text))
    target = extract_features(extract_clean_text(target_text))
    vocabulary = sorted(source["ending_counts"].keys() | target["ending_counts"].keys())
    similarity = cosine_similarity(
        build_feature_vector(source, vocabulary),
        build_feature_vector(target, vocabulary),
    )
    if similarity >= 0.85:
        assessment = (
            "文体の類似性が極めて高いです（同一著者または強い依拠・リライトの疑い）"
        )
    elif similarity >= 0.70:
        assessment = "文体に類似した傾向が見られます"
    else:
        assessment = "文体に明確な相違が見られます"
    return {
        "source_features": source,
        "target_features": target,
        "vocabulary": vocabulary,
        "similarity": similarity,
        "assessment": assessment,
    }
