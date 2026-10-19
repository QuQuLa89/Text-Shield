"""UTF-8署名をゼロ幅文字で埋め込み・復元します。"""

import re

from .utils import bits_to_text, frontmatter_end, protected_mask, text_to_bits

ZERO = "\u200b"
ONE = "\u200c"
DELIMITER = "\u200d"
WATERMARK_PATTERN = re.compile(f"{DELIMITER}([{ZERO}{ONE}]+){DELIMITER}")


def embed_watermark(text: str, signature: str = "QuQuLa89") -> str:
    text = text.removeprefix("\ufeff")
    if not signature:
        raise ValueError("署名は空にできません。")
    record = (
        DELIMITER
        + text_to_bits(signature).translate(str.maketrans({"0": ZERO, "1": ONE}))
        + DELIMITER
    )
    mask = protected_mask(text)
    # 各行の最後の通常文字の後へ配置し、hard break用の末尾空白を保ちます。
    positions = []
    offset = 0
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n \t")
        if content:
            end = offset + len(content)
            if (
                not mask[end - 1]
                and (content[-1].isalnum() or content[-1] in "。！？!?、,.;:")
                and not re.match(r"^ {0,3}(?:#{1,6}\s|[-+*]\s|>\s|\d+[.)]\s)", content)
            ):
                positions.append(end)
        offset += len(line)
    if positions:
        # 独立した完全な署名を最大3か所へ分散し、部分コピーでも復元可能にします。
        positions = sorted(
            {positions[0], positions[len(positions) // 2], positions[-1]}
        )
    else:
        # コードだけの原稿では独立した非表示リンク定義内へ格納します。
        newline = "\r\n" if "\r\n" in text else "\n"
        index = frontmatter_end(text)
        prefix = text[:index]
        if prefix and not prefix.endswith(("\n", "\r", "\ufeff")):
            prefix += newline
        return (
            prefix
            + f"[text-shield-watermark]: # ({record}){newline}{newline}"
            + text[index:]
        )
    for index in reversed(positions):
        text = text[:index] + record + text[index:]
    return text


def extract_watermark(text: str) -> list[str]:
    signatures = []
    for match in WATERMARK_PATTERN.finditer(text):
        try:
            signature = bits_to_text(
                match[1].translate(str.maketrans({ZERO: "0", ONE: "1"}))
            )
        except (ValueError, UnicodeDecodeError):
            continue
        if signature not in signatures:
            signatures.append(signature)
    return signatures


def strip_watermarks(text: str) -> str:
    """本ツールの格納行と、正しく復元できる透かしのみ取り除きます。"""
    text = re.sub(
        rf"(?m)^\[text-shield-watermark\]: # \({WATERMARK_PATTERN.pattern}\)\r?\n\r?\n",
        "",
        text,
    )

    def remove(match: re.Match) -> str:
        return "" if extract_watermark(match[0]) else match[0]

    return WATERMARK_PATTERN.sub(remove, text)
