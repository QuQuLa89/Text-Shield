"""Markdownの参照リンク定義としてオプトアウト宣言を挿入します。"""

import re
from urllib.parse import quote

from .utils import frontmatter_end


def inject_opt_out(
    text: str, author: str = "QuQuLa89", directive: str = "EU-DSM-Directive-Art-4"
) -> str:
    # BOMが参照定義の先頭文字として解釈されるレンダラーを避けます。
    text = text.removeprefix("\ufeff")
    if not author or not directive:
        raise ValueError("著作者名と指令名は空にできません。")
    if re.search(r"(?m)^ {0,3}\[//\]:", text):
        raise ValueError(
            "既存の[//]参照定義があります。競合を避けるため処理を中止します。"
        )
    # 括弧・改行・区切り文字を符号化して定義外への注入を防ぎます。
    fields = (
        f"Author={quote(author, safe='')}; Machine-Readable-Opt-Out=True; "
        "License=All-Rights-Reserved; "
        f"Directive={quote(directive, safe='')}; "
        "Prohibition=Style-Imitation,Fine-Tuning"
    )
    newline = "\r\n" if "\r\n" in text else "\n"
    declaration = f"[//]: # (AI-TRAINING-OPT-OUT: {fields}){newline}{newline}"
    index = frontmatter_end(text)
    prefix = text[:index]
    if prefix and not prefix.endswith(("\n", "\r", "\ufeff")):
        prefix += newline
    return prefix + declaration + text[index:]
