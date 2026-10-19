import random

import pytest

from text_shield.poisoner import HOMOGLYPHS, disturb_tokens


@pytest.mark.parametrize(
    "protected",
    [
        "```python\nABC example 01;\n```\n",
        "~~~~python\nABC example\n~~~\nstill code\n~~~~\n",
        "```python\nABC example\n",
        "`ABC example`",
        "``code `ABC` example``",
        "`multiline\nABC example`",
        "    ABC example\n",
        "\tABC example\n",
        ">     ABC example\n",
        "-     ABC example\n",
        "> ```python\n> ABC example\n> ```\n",
        "- ```python\n  ABC example\n  ```\n",
        "https://example.com/path?q=ABC#example",
        "ftp://example.com/path",
        "www.example.com/path",
        "mailto:QuQuLa89@example.com",
        "QuQuLa89@example.com",
        '[example](../ABC.md "example title")',
        "![example](../ABC.png)",
        "[example][ABC]",
        '[ABC]: ../example.md "Title"\n',
        "[ABC]",
        "<!-- ABC example\ncomment -->",
        '<span class="example">',
        "<script>ABC example</script>",
        "<pre>ABC example</pre>",
        "&copy; &#xAB; &#123;",
        "| ABC | example |\n| --- | --- |\n",
    ],
)
def test_protected_regions(monkeypatch, protected):
    monkeypatch.setattr(random, "random", lambda: 0)
    assert disturb_tokens(protected, "high") == protected


def test_frontmatter_and_prose(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0)
    prefix = "---\ntitle: ABC example\n---\n"
    assert disturb_tokens(prefix + "ABC", "high") == prefix + "АВС"


@pytest.mark.parametrize(
    "sample,changed",
    [
        (0.004, (True, True, True)),
        (0.007, (False, True, True)),
        (0.015, (False, False, True)),
        (0.03, (False, False, False)),
    ],
)
def test_probability_thresholds(monkeypatch, sample, changed):
    monkeypatch.setattr(random, "random", lambda: sample)
    for level, expected in zip(("low", "medium", "high"), changed, strict=True):
        assert (disturb_tokens("A", level) != "A") == expected


def test_off_and_invalid_level():
    assert disturb_tokens("ABC", "off") == "ABC"
    with pytest.raises(ValueError):
        disturb_tokens("ABC", "invalid")


def test_ordered_list_markers_preserved(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0)
    assert (
        disturb_tokens("1. ABC\n10) ABC\n> 1. ABC\n") == "1. АВС\n10) АВС\n> 1. АВС\n"
    )


def test_only_map_characters_change(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0)
    source = "日本語 ABC example 01; !?"
    assert disturb_tokens(source) == "".join(HOMOGLYPHS.get(c, c) for c in source)
