"""ハッシュ・バイナリ変換と、変更対象外のMarkdown領域を扱います。"""

import hashlib
import re


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def text_to_bits(text: str) -> str:
    return "".join(f"{byte:08b}" for byte in text.encode("utf-8"))


def bits_to_text(bits: str) -> str:
    if not bits or len(bits) % 8 or set(bits) - {"0", "1"}:
        raise ValueError("バイナリ列は空でない8ビット単位の0と1が必要です。")
    return bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8)).decode(
        "utf-8"
    )


def frontmatter_end(text: str) -> int:
    """BOMを含む先頭のYAML Frontmatterの終端を返します。"""
    start = 1 if text.startswith("\ufeff") else 0
    lines = text[start:].splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return start
    offset = start + len(lines[0])
    for line in lines[1:]:
        offset += len(line)
        if line.rstrip("\r\n") in {"---", "..."}:
            return offset
    raise ValueError("YAML Frontmatterの終端がありません。")


def protected_mask(text: str) -> bytearray:
    """構文・コード・リンク・HTMLを保守的に変更対象から除外します。"""
    mask = bytearray(len(text))

    def mark(start: int, end: int) -> None:
        mask[start:end] = b"\1" * (end - start)

    mark(0, frontmatter_end(text))
    fence = None
    offset = 0
    # 引用やリスト内のフェンスも保守的に認識します。
    fence_re = re.compile(r"^[ \t]*(?:>[ \t]*)*(?:[-+*] |\d+[.)] )?(`{3,}|~{3,})")
    for line in text.splitlines(keepends=True):
        match = fence_re.match(line)
        unquoted = re.sub(r"^ {0,3}(?:> ?)+", "", line)
        if fence:
            mark(offset, offset + len(line))
            if (
                match
                and match[1][0] == fence[0]
                and len(match[1]) >= len(fence)
                and not line[match.end() :].strip()
            ):
                fence = None
        elif match:
            fence = match[1]
            mark(offset, offset + len(line))
        elif (
            unquoted.expandtabs(4).startswith("    ")
            or re.match(r"^ {0,3}(?:[-+*]|\d+[.)]) (?: {4}|\t)", unquoted)
            or re.match(r"^ {0,3}\[[^\]]+\]:", line)
            or re.match(r"^\s*(?:[-*_]\s*){3,}$", line)
            or "|" in line
        ):
            mark(offset, offset + len(line))
        marker = re.match(
            r"^ {0,3}(?:>[ \t]*)*(?:\d+[.)][ \t]+|[-+*][ \t]+|#{1,6}[ \t]+)",
            line,
        )
        if marker:
            mark(offset, offset + marker.end())
        offset += len(line)

    # 同じ長さのバッククォートで囲まれたインラインコードです。
    ticks = list(re.finditer(r"`+", text))
    i = 0
    while i < len(ticks):
        opening = ticks[i]
        if mask[opening.start()]:
            i += 1
            continue
        closing = next(
            (
                j
                for j in range(i + 1, len(ticks))
                if ticks[j][0] == opening[0] and not mask[ticks[j].start()]
            ),
            None,
        )
        if closing is not None:
            mark(opening.start(), ticks[closing].end())
            i = closing + 1
        else:
            mark(opening.start(), opening.end())
            i += 1

    patterns = (
        r"<!--.*?(?:-->|\Z)",
        r"<(?:script|style|pre|code)\b[^>]*>.*?(?:</(?:script|style|pre|code)>|\Z)",
        r"<[^>\n]+>",
        r"(?:[a-zA-Z][a-zA-Z0-9+.-]*://|mailto:|www\.)[^\s<>`]+",
        r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}",
        # ラベルも含めて保護し、括弧を含むリンクは行末まで保護します。
        r"!?\[[^\]\n]*\](?:\([^\n]*|\[[^\]\n]*\])",
        r"\[[^\]\n]+\]",
        r"&(?:#\d+|#x[\da-fA-F]+|\w+);",
        r"\\[^\n]",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.DOTALL | re.IGNORECASE):
            mark(*match.span())
    return mask
