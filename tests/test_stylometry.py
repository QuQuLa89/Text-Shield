import math

import pytest

from text_shield.cli import main
from text_shield.stylometry import (
    build_feature_vector,
    compare_texts,
    cosine_similarity,
    extract_clean_text,
    extract_features,
)
from text_shield.watermark import embed_watermark


@pytest.mark.parametrize(
    "markdown,expected",
    [
        ("", ""),
        ("\ufeff# 見出し\n\n本文です。", "見出し\n\n本文です。"),
        ("## 見出し", "見出し"),
        ("本文`code`です。", "本文です。"),
        ("本文``code ` inside``です。", "本文です。"),
        ("![説明](https://example.com/image.png)本文", "本文"),
        ("[本文](https://example.com/path_(a))", "本文"),
        ("<span class='a'>本文</span>", "本文"),
        ("<!-- 隠れた\nコメント -->本文", "本文"),
        ("- 本文\n* 本文\n+ 本文\n1. 本文\n2) 本文", "本文\n本文\n本文\n本文\n本文"),
        ("> > 本文\n> - 引用", "本文\n引用"),
        ("---\n***\n___\n- - -\n* * *\n_ _ _\n本文", "本文"),
        ("---\r\n***\r\n本文", "本文"),
        ("C#やa-bはそのまま", "C#やa-bはそのまま"),
    ],
)
def test_extract_clean_text(markdown, expected):
    assert extract_clean_text(markdown) == expected


@pytest.mark.parametrize("fence", ["```", "````", "~~~~"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_code_fences(fence, newline):
    markdown = newline.join(["前の本文", fence + "python", "コード", fence, "後の本文"])
    clean = extract_clean_text(markdown)
    assert clean.split() == ["前の本文", "後の本文"]
    assert extract_features(clean)["total_sentences"] == 2


def test_shorter_or_different_fence_does_not_close_code_block():
    markdown = "本文です。\n````\n```\nコード\n~~~~\n````\n続きです。"
    assert extract_clean_text(markdown).split() == ["本文です。", "続きです。"]


@pytest.mark.parametrize("prefix", ["", "> ", "- "])
def test_unclosed_code_fence_is_excluded(prefix):
    assert extract_clean_text(f"本文です。\n{prefix}```\nコードだけ") == "本文です。"


def test_watermark_removal_and_non_mutation():
    original = "本文の文体です。\n何度も解析します。"
    marked = embed_watermark(original, "QuQuLa89")
    assert extract_clean_text(marked) == original
    assert compare_texts(original, marked)["similarity"] == pytest.approx(1)
    assert "\u200d" in marked


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize("terminator", ["---", "..."])
def test_frontmatter_and_reference_definitions_are_excluded(newline, terminator):
    body = "Pythonで文体を調べます。"
    markdown = newline.join(
        [
            "\ufeff---",
            "title: Metadata should not count",
            terminator,
            "[//]: # (AI-TRAINING-OPT-OUT: Author=QuQuLa89)",
            "   [reference]: https://example.com",
            body,
        ]
    )
    assert extract_clean_text(markdown) == body


@pytest.mark.parametrize("frontmatter", [False, True])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize(
    "body", ["# 文体\nPythonを使います。春である。", "```python\nx = 1\n```\n"]
)
def test_protect_preserves_stylometry_profile(tmp_path, frontmatter, newline, body):
    text = ("---\ntitle: Metadata\n---\n" if frontmatter else "") + body
    text = text.replace("\n", newline)
    source = tmp_path / "source.md"
    protected = tmp_path / "protected.md"
    source.write_bytes(text.encode("utf-8"))
    assert (
        main(
            [
                "protect",
                str(source),
                "-o",
                str(protected),
                "--author",
                "QuQuLa89",
                "--poison-level",
                "off",
            ]
        )
        == 0
    )
    marked = protected.read_bytes().decode("utf-8")
    assert "AI-TRAINING-OPT-OUT" in marked
    assert extract_features(extract_clean_text(marked)) == extract_features(
        extract_clean_text(text)
    )


@pytest.mark.parametrize("text", ["", " \t\r\n\u3000"])
def test_empty_features(text):
    features = extract_features(text)
    assert features["total_chars"] == features["total_sentences"] == 0
    assert features["ending_counts"] == {}
    assert features["top_endings"] == []
    assert all(value == 0.0 for key, value in features.items() if key.endswith("ratio"))
    assert features["avg_sentence_len"] == 0.0
    assert build_feature_vector(features, ["ます"]) == [0.0] * 8


def test_character_and_punctuation_ratios():
    features = extract_features(" 漢 あ\tア A1 、,!?\u3000")
    assert features["total_chars"] == 9
    for key in ("kanji_ratio", "hiragana_ratio", "katakana_ratio"):
        assert features[key] == pytest.approx(1 / 9)
    for key in ("latin_ratio", "comma_ratio", "exclamation_ratio"):
        assert features[key] == pytest.approx(2 / 9)
    assert features["avg_sentence_len"] == 9
    assert features["ending_counts"] == {"アA1": 1}


def test_character_range_boundaries():
    features = extract_features("\u4e00\u9fff\u3040\u309f\u30a0\u30ffazAZ09")
    assert features["total_chars"] == 12
    assert features["kanji_ratio"] == features["hiragana_ratio"] == 2 / 12
    assert features["katakana_ratio"] == 2 / 12
    assert features["latin_ratio"] == 6 / 12


def test_sentence_length_filter_and_split_rules():
    features = extract_features(
        "あいう。あ い う え！かきくけ？さしすせ\nたちつて\rなにぬね\r\n"
    )
    assert features["total_sentences"] == 5
    assert features["avg_sentence_len"] == 4
    # ASCIIの!?は指定の文分割パターンに含まれません。
    assert extract_features("abcd!efgh?")["total_sentences"] == 1


def test_endings_ignore_punctuation_and_keep_top_five():
    features = extract_features(
        "春である。夏である。秋だろう。冬とする。」\n花になる。鳥がいる。夢を見る。"
    )
    assert features["ending_counts"] == {
        "である": 2,
        "だろう": 1,
        "とする": 1,
        "になる": 1,
        "がいる": 1,
        "を見る": 1,
    }
    assert len(features["top_endings"]) == 5
    assert features["top_endings"][0] == ("である", 2)


def test_short_endings_and_punctuation_only_sentences():
    features = extract_features("ab!!\na!!!\n????")
    assert features["total_sentences"] == 3
    assert features["ending_counts"] == {"ab": 1}


@pytest.mark.parametrize(
    "length,comma,exclamation,expected",
    [
        (50, 0.03, 0.01, [0.5, 0.3, 0.2]),
        (100, 0.1, 0.05, [1.0, 1.0, 1.0]),
        (250, 0.5, 0.5, [1.0, 1.0, 1.0]),
    ],
)
def test_vector_normalization_and_vocabulary_order(
    length, comma, exclamation, expected
):
    features = extract_features("春である。夏である。秋だろう。冬とする。")
    features.update(
        avg_sentence_len=length, comma_ratio=comma, exclamation_ratio=exclamation
    )
    before = features.copy()
    vector = build_feature_vector(features, ["だろう", "未知", "である"])
    assert vector[:4] == [
        features[key]
        for key in ("kanji_ratio", "hiragana_ratio", "katakana_ratio", "latin_ratio")
    ]
    assert vector[4:7] == pytest.approx(expected)
    assert vector[7:] == [0.25, 0, 0.5]
    assert features == before


@pytest.mark.parametrize(
    "left,right,expected",
    [
        ([], [], 1.0),
        ([0, 0], [0, 0], 1.0),
        ([0, 0], [1, 0], 0.0),
        ([1, 0], [0, 0], 0.0),
        ([1, 0], [0, 1], 0.0),
        ([1, 1], [1, 0], 1 / math.sqrt(2)),
        ([1, 2, 3], [2, 4, 6], 1.0),
        ([1e200, 1e200], [1e200, 1e200], 1.0),
        ([1e-200], [1e-200], 1.0),
    ],
)
def test_cosine_similarity(left, right, expected):
    result = cosine_similarity(left, right)
    assert result == pytest.approx(expected)
    assert 0 <= result <= 1
    assert result == pytest.approx(cosine_similarity(right, left))


def test_cosine_rejects_mismatched_dimensions():
    with pytest.raises(ValueError, match="次元数"):
        cosine_similarity([1], [1, 2])


@pytest.mark.parametrize(
    "score,message",
    [
        (1.0, "文体の類似性が極めて高いです（同一著者または強い依拠・リライトの疑い）"),
        (
            0.85,
            "文体の類似性が極めて高いです（同一著者または強い依拠・リライトの疑い）",
        ),
        (0.849999, "文体に類似した傾向が見られます"),
        (0.70, "文体に類似した傾向が見られます"),
        (0.699999, "文体に明確な相違が見られます"),
        (0.0, "文体に明確な相違が見られます"),
    ],
)
def test_assessment_thresholds(monkeypatch, score, message):
    monkeypatch.setattr("text_shield.stylometry.cosine_similarity", lambda a, b: score)
    result = compare_texts("春である。", "秋だろう。")
    assert result["similarity"] == score
    assert result["assessment"] == message


def test_comparison_uses_all_endings_and_shared_sorted_vocabulary():
    source = "春である。夏だろう。秋とする。冬になる。鳥がいる。夢を見る。"
    target = "朝でした。夜でした。"
    result = compare_texts(source, target)
    assert result["vocabulary"] == sorted(
        ["である", "だろう", "とする", "になる", "がいる", "を見る", "でした"]
    )
    assert result["source_features"] == extract_features(source)
    assert result["target_features"] == extract_features(target)
    assert 0 <= result["similarity"] < 1
    assert compare_texts(target, source)["similarity"] == pytest.approx(
        result["similarity"]
    )


@pytest.mark.parametrize(
    "source,target,expected",
    [
        ("同じ文体である。", "同じ文体である。", 1.0),
        ("", "", 1.0),
        ("```\nコード\n```", "", 1.0),
        ("", "こちらが本文です。", 0.0),
    ],
)
def test_comparison_integration(source, target, expected):
    assert compare_texts(source, target)["similarity"] == pytest.approx(expected)


def test_clearly_different_styles():
    result = compare_texts("春である。夏である。", "ABCDEFGHIJKL!")
    assert result["similarity"] < 0.7
    assert result["assessment"] == "文体に明確な相違が見られます"
