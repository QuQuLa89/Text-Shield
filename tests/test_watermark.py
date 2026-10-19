import re

import pytest
from markdown_it import MarkdownIt

from text_shield.utils import bits_to_text, text_to_bits
from text_shield.watermark import (
    DELIMITER,
    ONE,
    ZERO,
    embed_watermark,
    extract_watermark,
    strip_watermarks,
)


@pytest.mark.parametrize("signature", ["QuQuLa89", "日本語の署名🌟", "a", "0" * 200])
@pytest.mark.parametrize(
    "text", ["Hello world", "本文です。\n二行目です。\n三行目です。\n", ""]
)
def test_roundtrip(text, signature):
    result = embed_watermark(text, signature)
    assert extract_watermark(result) == [signature]
    renderer = MarkdownIt()
    assert re.sub(
        f"[{ZERO}{ONE}{DELIMITER}]", "", renderer.render(result)
    ) == renderer.render(text)
    assert strip_watermarks(result) == text


def test_default_and_partial_copy():
    result = embed_watermark("first line\nsecond line\nthird line\n")
    for line in result.splitlines():
        assert extract_watermark(line) == ["QuQuLa89"]


def test_deduplicates_and_recovers_distinct_signatures():
    result = embed_watermark("本文", "QuQuLa89") + embed_watermark("本文", "別の署名")
    assert extract_watermark(result) == ["QuQuLa89", "別の署名"]


@pytest.mark.parametrize("bits", ["0", "11111111", "11000000" * 2])
def test_malformed_watermark_is_ignored(bits):
    malformed = (
        DELIMITER + bits.translate(str.maketrans({"0": ZERO, "1": ONE})) + DELIMITER
    )
    valid = embed_watermark("本文")
    assert extract_watermark(malformed + valid) == ["QuQuLa89"]
    assert strip_watermarks(malformed) == malformed


@pytest.mark.parametrize(
    "text",
    [
        "```python\nprint('text')\n```\n",
        "---\ntitle: Example\n---\n# Title\n",
        "    indented code\n",
        "[link](https://example.com)\n",
        "---\n",
    ],
)
def test_fallback_preserves_markdown(text):
    if text == "---\n":
        with pytest.raises(ValueError):
            embed_watermark(text)
        return
    result = embed_watermark(text)
    assert extract_watermark(result) == ["QuQuLa89"]
    assert strip_watermarks(result) == text
    assert MarkdownIt().render(result) == MarkdownIt().render(text)


def test_watermark_preserves_code_urls_and_hard_break():
    text = (
        "text  \r\n`print('x')`\r\nhttps://example.com/test\r\n```\r\ncode\r\n```\r\n"
    )
    result = embed_watermark(text)
    assert "  \r\n" in result
    assert "`print('x')`" in result
    assert "https://example.com/test\r\n" in result
    assert "```\r\ncode\r\n```\r\n" in result
    assert strip_watermarks(result) == text


@pytest.mark.parametrize("bits", ["", "0", "0000000x", "2" * 8])
def test_invalid_bits(bits):
    with pytest.raises(ValueError):
        bits_to_text(bits)


def test_utf8_bits_and_empty_signature():
    assert bits_to_text(text_to_bits("署名🌟")) == "署名🌟"
    with pytest.raises(ValueError):
        embed_watermark("text", "")
