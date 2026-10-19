import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from markdown_it import MarkdownIt

from text_shield.cli import PAYLOAD_PREFIX, resolve_author
from text_shield.utils import sha256_text
from text_shield.watermark import embed_watermark, extract_watermark, strip_watermarks


def run_cli(*args, cwd=None, env_overrides=None):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["TEXT_SHIELD_AUTHOR"] = "QuQuLa89"
    for key, value in (env_overrides or {}).items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(
        [sys.executable, "-m", "text_shield", *map(str, args)],
        cwd=cwd,
        env=env,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )


@pytest.fixture
def files(tmp_path):
    source = tmp_path / "元原稿.md"
    output = tmp_path / "保護済み.md"
    source.write_bytes("# Title\r\n\r\nQuQuLa89の原稿です。\r\n".encode())
    return source, output


def test_end_to_end(files, tmp_path):
    source, output = files
    original = source.read_bytes()
    result = run_cli(
        "protect",
        source,
        "-o",
        output,
        "--author",
        "QuQuLa89",
        "--poison-level",
        "off",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert not result.stdout
    assert source.read_bytes() == original
    protected = output.read_bytes().decode()
    assert "\r\n" in protected
    signature = extract_watermark(protected)[0]
    payload = json.loads(signature[len(PAYLOAD_PREFIX) :])
    assert payload["author"] == "QuQuLa89"
    assert payload["source_sha256"] == sha256_text(original.decode())
    assert payload["content_sha256"] == sha256_text(strip_watermarks(protected))
    result = run_cli("verify", output, "--original", source)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "元原稿照合: 一致" in result.stdout
    assert "本文照合: 一致" in result.stdout
    assert "UTC時刻:" in result.stdout
    result = run_cli("inspect", output, "--limit", "2")
    assert result.returncode == 0
    assert "不可視文字数:" in result.stdout
    assert "位置=" in result.stdout
    assert "表示上限" in result.stdout


def test_stdout_and_unicode_author(files):
    source, _ = files
    result = run_cli(
        "protect", source, "--author", "QuQuLa89🌟", "--poison-level", "off"
    )
    assert result.returncode == 0
    assert "QuQuLa89🌟" in extract_watermark(result.stdout)[0]
    assert "AI-TRAINING-OPT-OUT" in result.stdout


@pytest.mark.parametrize(
    "content",
    [
        "",
        "```\nABC\n```\n",
        "---\ntitle: ABC\n---\n",
        "# Heading\n",
        "\ufeff# Heading\n",
        "\ufeff```\nABC\n```\n",
    ],
)
def test_structural_only_input(tmp_path, content):
    source = tmp_path / "in.md"
    output = tmp_path / "out.md"
    source.write_text(content, encoding="utf-8")
    assert (
        run_cli("protect", source, "-o", output, "--poison-level", "off").returncode
        == 0
    )
    result = run_cli("verify", output, "--original", source)
    assert result.returncode == 0, result.stdout
    if not content.startswith("---"):
        assert MarkdownIt().render(
            output.read_text(encoding="utf-8")
        ) == MarkdownIt().render(content.removeprefix("\ufeff"))


def test_tamper_and_wrong_original(files, tmp_path):
    source, output = files
    assert run_cli("protect", source, "-o", output).returncode == 0
    other = tmp_path / "other.md"
    other.write_text("別の原稿", encoding="utf-8")
    result = run_cli("verify", output, "--original", other)
    assert result.returncode == 1
    assert "元原稿照合: 不一致" in result.stdout
    with output.open("a", encoding="utf-8") as stream:
        stream.write("改変")
    result = run_cli("verify", output)
    assert result.returncode == 1
    assert "本文照合: 不一致" in result.stdout


def test_existing_output_and_input_are_not_overwritten(files):
    source, output = files
    output.write_text("既存内容", encoding="utf-8")
    original = source.read_bytes()
    assert run_cli("protect", source, "-o", output).returncode == 2
    assert output.read_text(encoding="utf-8") == "既存内容"
    assert run_cli("protect", source, "-o", source).returncode == 2
    assert source.read_bytes() == original


def test_double_protection_rejected(files, tmp_path):
    source, output = files
    assert run_cli("protect", source, "-o", output).returncode == 0
    again = tmp_path / "again.md"
    assert run_cli("protect", output, "-o", again).returncode == 2
    assert not again.exists()


@pytest.mark.parametrize(
    "signature",
    [
        "QuQuLa89",
        PAYLOAD_PREFIX + "invalid",
        PAYLOAD_PREFIX + "null",
        PAYLOAD_PREFIX + "{}",
        PAYLOAD_PREFIX + '{"author":12}',
    ],
)
def test_legacy_and_malformed_metadata(tmp_path, signature):
    path = tmp_path / "metadata.md"
    path.write_text(embed_watermark("本文", signature), encoding="utf-8")
    result = run_cli("verify", path)
    assert result.returncode == 1
    assert "Traceback" not in result.stderr


def test_missing_invalid_utf8_and_no_watermark(tmp_path):
    assert run_cli("protect", tmp_path / "missing.md").returncode == 2
    path = tmp_path / "input.md"
    path.write_bytes(b"\xff")
    assert run_cli("verify", path).returncode == 2
    path.write_text("本文", encoding="utf-8")
    assert run_cli("verify", path).returncode == 1


@pytest.mark.parametrize("newline,position", [("\n", 2), ("\r\n", 3)])
def test_inspect_candidates_positions_and_color(tmp_path, newline, position):
    path = tmp_path / "inspect.md"
    path.write_bytes(f"A{newline}\u200bА".encode())
    result = run_cli("inspect", path, "--color", "never")
    assert "不可視文字数: 1" in result.stdout
    assert "ホモグリフ候補数: 1" in result.stdout
    assert f"位置={position} 行=2 列=1 U+200B" in result.stdout
    assert "\033[" not in result.stdout
    assert "\033[" in run_cli("inspect", path, "--color", "always").stdout
    assert run_cli("inspect", path, "--limit", "-1").returncode == 2


def test_help_version_and_bad_level(files):
    source, _ = files
    assert "protect" in run_cli("--help").stdout
    assert run_cli("--version").stdout.strip() == "0.1.0"
    assert run_cli("protect", source, "--poison-level", "invalid").returncode == 2


def test_installed_entrypoint(tmp_path):
    executable = Path(sys.executable).parent / (
        "text-shield.exe" if os.name == "nt" else "text-shield"
    )
    result = subprocess.run(
        [str(executable), "--version"], cwd=tmp_path, capture_output=True, check=False
    )
    assert result.returncode == 0
    assert result.stdout.strip() == b"0.1.0"


@pytest.mark.parametrize(
    "explicit,environment,git_name,expected",
    [
        ("QuQuLa89", "環境変数の名前", "Gitの名前", "QuQuLa89"),
        (None, " QuQuLa89 🌟 ", "Gitの名前", "QuQuLa89 🌟"),
        (None, None, " QuQuLa89 日本語 ", "QuQuLa89 日本語"),
        (None, "  ", "QuQuLa89", "QuQuLa89"),
    ],
)
def test_author_priority_and_payload(
    files, tmp_path, explicit, environment, git_name, expected
):
    source, output = files
    # Git設定をプロセス内で指定し、実際のローカル・グローバル設定を変更しません。
    env = {
        "TEXT_SHIELD_AUTHOR": environment,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "user.name",
        "GIT_CONFIG_VALUE_0": git_name,
    }
    options = [] if explicit is None else ["--author", explicit]
    result = run_cli(
        "protect",
        source,
        "-o",
        output,
        "--poison-level",
        "off",
        *options,
        cwd=tmp_path,
        env_overrides=env,
    )
    assert result.returncode == 0, result.stderr
    signature = extract_watermark(output.read_text(encoding="utf-8"))[0]
    assert json.loads(signature[len(PAYLOAD_PREFIX) :])["author"] == expected
    verified = run_cli("verify", output, "--original", source)
    assert verified.returncode == 0, verified.stdout + verified.stderr
    assert f"著作者: {json.dumps(expected, ensure_ascii=False)}" in verified.stdout


@pytest.mark.parametrize("environment,git_name", [(None, ""), ("  ", " \t ")])
def test_missing_author_does_not_write(files, tmp_path, environment, git_name):
    source, output = files
    original = source.read_bytes()
    result = run_cli(
        "protect",
        source,
        "-o",
        output,
        cwd=tmp_path,
        env_overrides={
            "TEXT_SHIELD_AUTHOR": environment,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "user.name",
            "GIT_CONFIG_VALUE_0": git_name,
        },
    )
    assert result.returncode == 2
    assert "著作者名が指定されていません" in result.stderr
    assert "--author" in result.stderr
    assert "TEXT_SHIELD_AUTHOR" in result.stderr
    assert "git config user.name" in result.stderr
    assert "Traceback" not in result.stderr
    assert not result.stdout
    assert not output.exists()
    assert source.read_bytes() == original


@pytest.mark.parametrize("author", ["", " \t "])
def test_empty_explicit_author_is_rejected(files, author):
    source, output = files
    result = run_cli("protect", source, "-o", output, "--author", author)
    assert result.returncode == 2
    assert "著作者名が指定されていません" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("author", [" QuQuLa89 ", None])
def test_explicit_or_environment_author_does_not_invoke_git(monkeypatch, author):
    monkeypatch.setenv("TEXT_SHIELD_AUTHOR", "QuQuLa89")

    def unexpected_git(*args, **kwargs):
        pytest.fail("著作者名が解決済みの場合はGitを呼び出しません。")

    monkeypatch.setattr("text_shield.cli.subprocess.run", unexpected_git)
    assert resolve_author(author) == "QuQuLa89"


@pytest.mark.parametrize(
    "failure",
    [
        FileNotFoundError("git"),
        subprocess.TimeoutExpired(["git", "config", "user.name"], 5),
        UnicodeError("invalid UTF-8"),
        subprocess.CompletedProcess([], 1, stdout="", stderr="not configured"),
    ],
)
def test_unavailable_git_produces_missing_author_error(monkeypatch, failure):
    monkeypatch.delenv("TEXT_SHIELD_AUTHOR", raising=False)

    def git_config(*args, **kwargs):
        if isinstance(failure, Exception):
            raise failure
        return failure

    monkeypatch.setattr("text_shield.cli.subprocess.run", git_config)
    with pytest.raises(ValueError, match="著作者名が指定されていません"):
        resolve_author(None)
