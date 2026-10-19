"""text-shield CLIです。"""

import argparse
import bisect
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .injector import inject_opt_out
from .poisoner import HOMOGLYPHS, PROBABILITIES, disturb_tokens
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


def protect(args: argparse.Namespace) -> int:
    source = read_text(args.input_file)
    if extract_watermark(source):
        raise ValueError("既存の透かしがあります。元原稿から処理してください。")
    body = disturb_tokens(inject_opt_out(source, args.author), args.poison_level)
    payload = {
        "author": args.author,
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


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="")
    parser = argparse.ArgumentParser(
        description="Markdownに透かしとオプトアウト宣言を付与します。"
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    protect_parser = commands.add_parser("protect", help="原稿を処理します。")
    protect_parser.add_argument("input_file", type=Path)
    protect_parser.add_argument("-o", "--output", type=Path)
    protect_parser.add_argument("--author", default="QuQuLa89")
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
