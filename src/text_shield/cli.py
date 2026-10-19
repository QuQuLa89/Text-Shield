"""text-shield CLIです。"""

import argparse
import bisect
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .injector import inject_opt_out
from .poisoner import HOMOGLYPHS, PROBABILITIES, disturb_tokens
from .stylometry import compare_texts, extract_clean_text, extract_features
from .utils import sha256_text
from .watermark import (
    DELIMITER,
    ONE,
    ZERO,
    embed_watermark,
    extract_watermark,
    strip_watermarks,
)

PAYLOAD_PREFIX = "text-shield:v1:"


def read_text(path: Path) -> str:
    with path.open(encoding="utf-8", newline="") as stream:
        return stream.read()


def resolve_author(author: str | None) -> str:
    if author is None:
        author = os.environ.get("TEXT_SHIELD_AUTHOR", "").strip()
        if not author:
            try:
                result = subprocess.run(
                    ["git", "config", "user.name"],
                    capture_output=True,
                    encoding="utf-8",
                    check=False,
                    timeout=5,
                )
                if result.returncode == 0:
                    author = result.stdout.strip()
            except (OSError, UnicodeError, subprocess.TimeoutExpired):
                pass
    if not author or not author.strip():
        raise ValueError(
            "著作者名が指定されていません。--author オプションを指定するか、"
            "環境変数 TEXT_SHIELD_AUTHOR または git config user.name を"
            "設定してください。"
        )
    return author.strip()


def protect(args: argparse.Namespace) -> int:
    author = resolve_author(args.author)
    source = read_text(args.input_file)
    if extract_watermark(source):
        raise ValueError("既存の透かしがあります。元原稿から処理してください。")
    body = disturb_tokens(inject_opt_out(source, author), args.poison_level)
    payload = {
        "author": author,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_sha256": sha256_text(source),
        "content_sha256": sha256_text(body),
    }
    signature = PAYLOAD_PREFIX + json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    )
    output = embed_watermark(body, signature)
    if args.output:
        # 既存ファイルと入力原稿を上書きしません。
        with args.output.open("x", encoding="utf-8", newline="") as stream:
            stream.write(output)
    else:
        sys.stdout.write(output)
    return 0


def verify(args: argparse.Namespace) -> int:
    text = read_text(args.input_file)
    signatures = extract_watermark(text)
    if not signatures:
        print("復元可能な透かしが見つかりませんでした。")
        return 1
    current_hash = sha256_text(strip_watermarks(text))
    source_hash = sha256_text(read_text(args.original)) if args.original else None
    success = True
    for signature in signatures:
        if not signature.startswith(PAYLOAD_PREFIX):
            print(f"著作者署名: {json.dumps(signature, ensure_ascii=False)}")
            print("時刻・ハッシュ情報がないため、照合できません。")
            success = False
            continue
        try:
            payload = json.loads(signature[len(PAYLOAD_PREFIX) :])
            if (
                not isinstance(payload, dict)
                or not isinstance(payload.get("author"), str)
                or not payload["author"]
                or not isinstance(payload.get("timestamp"), str)
                or datetime.fromisoformat(payload["timestamp"]).utcoffset()
                != timezone.utc.utcoffset(None)
                or any(
                    not isinstance(payload.get(key), str)
                    or not re.fullmatch(r"[0-9a-f]{64}", payload[key])
                    for key in ("source_sha256", "content_sha256")
                )
            ):
                raise ValueError("透かしメタデータの形式が不正です。")
        except (ValueError, TypeError):
            print("透かしメタデータを読み取れませんでした。")
            success = False
            continue
        print(f"著作者: {json.dumps(payload['author'], ensure_ascii=False)}")
        print(f"UTC時刻: {payload['timestamp']}")
        print(f"元原稿SHA-256: {payload['source_sha256']}")
        matched = current_hash == payload["content_sha256"]
        print(f"本文SHA-256: {payload['content_sha256']}")
        print(f"本文照合: {'一致' if matched else '不一致'}")
        success &= matched
        if source_hash is not None:
            matched = source_hash == payload["source_sha256"]
            print(f"元原稿照合: {'一致' if matched else '不一致'}")
            success &= matched
        else:
            print("元原稿照合: 未実施（--originalで指定できます）")
    return 0 if success else 1


def inspect_text(args: argparse.Namespace) -> int:
    text = read_text(args.input_file)
    labels = {
        ZERO: "ZERO-WIDTH SPACE",
        ONE: "ZERO-WIDTH NON-JOINER",
        DELIMITER: "ZERO-WIDTH JOINER",
    }
    invisible_count = sum(char in labels for char in text)
    candidates = {value: key for key, value in HOMOGLYPHS.items()}
    print(f"不可視文字数: {invisible_count}")
    print(f"ホモグリフ候補数: {sum(char in candidates for char in text)}")
    print("位置は0始まりの文字インデックス、行・列は1始まりです。")
    newlines = [-1] + [i for i, char in enumerate(text) if char == "\n"]
    shown = 0
    use_color = args.color == "always" or (args.color == "auto" and sys.stdout.isatty())
    for index, char in enumerate(text):
        if char not in labels and char not in candidates:
            continue
        if shown >= args.limit:
            print("表示上限に達しました。--limitで変更できます。")
            break
        line = bisect.bisect_left(newlines, index)
        column = index - newlines[line - 1]
        label = labels.get(char, f"ホモグリフ候補（ASCII候補: {candidates.get(char)}）")
        detail = f"位置={index} 行={line} 列={column} U+{ord(char):04X} {label}"
        print(f"\033[33m{detail}\033[0m" if use_color else detail)
        shown += 1
    return 0


def stylometry(args: argparse.Namespace) -> int:
    source_text = read_text(args.input_file)
    if args.compare is not None:
        result = compare_texts(source_text, read_text(args.compare))
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        print("=== スタイロメトリー照合結果 ===")
        print(f"基準文書: {args.input_file}")
        print(f"比較文書: {args.compare}\n")
        print("指標                 基準文書        比較文書")
        print("-" * 50)
        for label, key, format_spec in (
            ("平均文長", "avg_sentence_len", ".1f"),
            ("読点比率", "comma_ratio", ".1%"),
            ("漢字比率", "kanji_ratio", ".1%"),
            ("ひらがな比率", "hiragana_ratio", ".1%"),
            ("カタカナ比率", "katakana_ratio", ".1%"),
            ("英数字比率", "latin_ratio", ".1%"),
            ("感嘆符・疑問符比率", "exclamation_ratio", ".1%"),
        ):
            suffix = "文字" if key == "avg_sentence_len" else ""
            source = format(result["source_features"][key], format_spec) + suffix
            target = format(result["target_features"][key], format_spec) + suffix
            print(f"{label:<16} {source:<14} {target}")
        print(f"\n文体コサイン類似度: {result['similarity']:.1%}")
        print(f"判定: {result['assessment']}")
    else:
        features = extract_features(extract_clean_text(source_text))
        if args.json:
            print(json.dumps(features, ensure_ascii=False, indent=2))
            return 0
        print(f"=== 文体プロファイル: {args.input_file} ===")
        print(
            f"総文字数: {features['total_chars']:,}文字 / "
            f"総文数: {features['total_sentences']:,}文"
        )
        print(
            f"平均文長: {features['avg_sentence_len']:.1f}文字 / "
            f"読点比率: {features['comma_ratio']:.1%}"
        )
        print("文字種比率:")
        for label, key in (
            ("漢字", "kanji_ratio"),
            ("ひらがな", "hiragana_ratio"),
            ("カタカナ", "katakana_ratio"),
            ("英数字", "latin_ratio"),
        ):
            print(f"  {label}: {features[key]:.1%}")
        print("頻出文末表現:")
        for index, (ending, count) in enumerate(features["top_endings"], start=1):
            print(f"  {index}. {ending} ({count / features['total_sentences']:.1%})")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="")
    parser = argparse.ArgumentParser(
        description="Markdownへの透かし付与・検証と文体分析を行います。"
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    protect_parser = commands.add_parser("protect", help="原稿を処理します。")
    protect_parser.add_argument("input_file", type=Path)
    protect_parser.add_argument("-o", "--output", type=Path)
    protect_parser.add_argument(
        "--author",
        default=None,
        help=(
            "著作者名。省略時はTEXT_SHIELD_AUTHOR、"
            "git config user.nameの順に取得します。"
        ),
    )
    protect_parser.add_argument(
        "--poison-level", choices=PROBABILITIES, default="medium"
    )
    protect_parser.set_defaults(handler=protect)
    verify_parser = commands.add_parser("verify", help="署名とハッシュを照合します。")
    verify_parser.add_argument("input_file", type=Path)
    verify_parser.add_argument(
        "--original", type=Path, help="元原稿のハッシュも照合します。"
    )
    verify_parser.set_defaults(handler=verify)
    inspect_parser = commands.add_parser(
        "inspect", help="不可視文字と同形文字の候補を表示します。"
    )
    inspect_parser.add_argument("input_file", type=Path)
    inspect_parser.add_argument("--limit", type=int, default=50)
    inspect_parser.add_argument(
        "--color", choices=("auto", "always", "never"), default="auto"
    )
    inspect_parser.set_defaults(handler=inspect_text)
    stylometry_parser = commands.add_parser(
        "stylometry", help="文体特徴量を抽出し、文書間の類似度を比較します。"
    )
    stylometry_parser.add_argument("input_file", type=Path)
    stylometry_parser.add_argument(
        "--compare", type=Path, help="比較するUTF-8文書を指定します。"
    )
    stylometry_parser.add_argument(
        "--json", action="store_true", help="解析・比較結果をJSONで出力します。"
    )
    stylometry_parser.set_defaults(handler=stylometry)
    args = parser.parse_args(argv)
    if getattr(args, "limit", 0) < 0:
        parser.error("--limitには0以上の値を指定してください。")
    try:
        return args.handler(args)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
