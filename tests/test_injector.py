import pytest
from markdown_it import MarkdownIt

from text_shield.injector import inject_opt_out


@pytest.mark.parametrize(
    "text",
    [
        "# Title\n\nParagraph\n\n- first\n- second\n",
        "```python\nprint('example')\n```\n",
        "[example](https://example.com)\n\n![image](image.png)\n",
        "first  \nsecond\n\n> quote\n",
        "",
    ],
)
def test_declaration_is_hidden_and_preserves_rendering(text):
    result = inject_opt_out(text)
    assert result.startswith("[//]: # (AI-TRAINING-OPT-OUT: Author=QuQuLa89;")
    assert "Machine-Readable-Opt-Out=True" in result
    assert "Directive=EU-DSM-Directive-Art-4" in result
    assert result.endswith(text)
    assert MarkdownIt().render(result) == MarkdownIt().render(text)


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize("terminator", ["---", "..."])
def test_frontmatter_bom_and_newline(newline, terminator):
    frontmatter = f"\ufeff---{newline}title: Original{newline}{terminator}{newline}"
    body = "# Heading" + newline
    result = inject_opt_out(frontmatter + body)
    assert result.startswith(frontmatter.removeprefix("\ufeff") + "[//]: # (")
    assert result.endswith(body)
    assert newline + newline + body in result


def test_unclosed_frontmatter_fails():
    with pytest.raises(ValueError, match="終端"):
        inject_opt_out("---\ntitle: broken\n")


def test_existing_reference_is_not_shadowed():
    with pytest.raises(ValueError, match="既存"):
        inject_opt_out("[//]: https://example.com\n\n[label][//]\n")


def test_fields_cannot_escape_hidden_definition():
    result = inject_opt_out("本文", "QuQuLa89)\n# Visible;", "custom)\n")
    assert "Author=QuQuLa89%29%0A%23%20Visible%3B" in result
    assert "Directive=custom%29%0A" in result
    assert MarkdownIt().render(result) == MarkdownIt().render("本文")


@pytest.mark.parametrize("author,directive", [("", "x"), ("x", "")])
def test_empty_fields_fail(author, directive):
    with pytest.raises(ValueError):
        inject_opt_out("text", author, directive)
