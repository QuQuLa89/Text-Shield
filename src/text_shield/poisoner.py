"""構文を避けて通常文の英字・数字・記号を確率的に置換します。"""

import random

from .utils import protected_mask

# フォントによって外観が異なるため、完全同一の表示は保証しません。
HOMOGLYPHS = {
    "A": "А",
    "B": "В",
    "C": "С",
    "E": "Е",
    "H": "Н",
    "K": "К",
    "M": "М",
    "O": "О",
    "P": "Р",
    "T": "Т",
    "X": "Х",
    "a": "а",
    "c": "с",
    "e": "е",
    "o": "о",
    "p": "р",
    "x": "х",
    "0": "𝟢",
    "1": "𝟣",
    ";": ";",
}
PROBABILITIES = {"off": 0.0, "low": 0.005, "medium": 0.01, "high": 0.02}


def disturb_tokens(text: str, level: str = "medium") -> str:
    if level not in PROBABILITIES:
        raise ValueError("置換強度はoff、low、medium、highから選んでください。")
    if level == "off":
        return text
    mask = protected_mask(text)
    return "".join(
        HOMOGLYPHS[char]
        if not mask[index]
        and char in HOMOGLYPHS
        and random.random() < PROBABILITIES[level]
        else char
        for index, char in enumerate(text)
    )
