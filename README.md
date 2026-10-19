# text-shield

Markdownやテキストに、学習利用のオプトアウト宣言、ゼロ幅文字の透かし、任意のホモグリフ置換を付与するCLIです。著作者名・埋め込み時刻・ハッシュの抽出と照合、不可視文字の位置の確認ができます。

作成者はQuQuLa89、バージョンは0.1.0です。Python 3.10以上、4.0未満で動作し、実行時の外部依存はありません。

## CLIとAgent Skillのハイブリッド配布

同じリポジトリにPython CLIと [Agent Skillの定義](skills/text-shield/SKILL.md) を同梱しています。ターミナルから直接使う場合はCLIを、自然言語で処理を依頼する場合はAgent Skillを導入してください。Agent Skillも実際の処理にはCLIを使うため、Python環境とCLIのインストールが必要です。

スキルはリポジトリ内の `skills/text-shield/` フォルダを各エージェントのスキル領域へ配置して導入します。`pip install .` だけでは、エージェントへのスキル登録は行われません。

## 🤖 AIエージェント向け一発インストールプロンプト

このリポジトリをcloneまたはZIPから展開してから、次の手順で `text-shield` フォルダのパスをコピーしてください。パスは、フォルダがどこにあるかを表す文字列です。

- **Windows**: 展開した `text-shield` フォルダを、Shiftキーを押しながら右クリックし、「パスのコピー」を選びます。Windows 11では、右クリックメニューの「パスのコピー」からもコピーできます。
- **macOS**: `text-shield` フォルダを、Optionキーを押しながら右クリックし、「“text-shield”のパス名をコピー」を選びます。

次のプロンプトのパス欄をコピーしたパスに、著作者名の欄を自分の名前やペンネームに置き換えてから、Claude CodeやAntigravityなどのチャットへ貼り付けてください。コピーしたパスの前後に引用符が付いている場合は、そのまま使えます。

Copy the folder path using the steps above. Replace the path and author placeholders below with that path and your name or pen name before sending the prompt to your AI agent.

### 日本語

```text
[ここにtext-shieldフォルダのパスを貼り付けてください] に取得したtext-shieldを、今使っているAIエージェントのAgent Skillとして導入してください。
著作者名は「[ここにあなたの著作者名（ペンネーム等）を貼り付けてください]」です。
README.mdとskills/text-shield/SKILL.mdを読み、Python 3.10以上、4.0未満で動くCLIを準備してください。リポジトリ内の.venvを使い、なければ作成し、そのPythonで -m pip install . を実行してください。
この環境のスキル探索先を確認し、skills/text-shield/を配置してください。共通スキルの実体がある環境では、その運用に合わせて参照を接続してください。既存のファイルやリンクがあれば削除・上書きせず、競合を報告してください。
配置したSKILL.mdの読み取りとCLIの --version、protect --help、verify --help、inspect --help を確認してください。新規の一時原稿で、上記の著作者名を --author に渡し、--poison-level off を指定してprotectを実行してください。続けてverifyに --original を指定して照合し、inspectを実行してください。元原稿が変更されていないこと、著作者名が指定どおりであること、本文と元原稿のハッシュが一致することを確認してください。
最後に配置先、CLIの実行パス、検証結果を教えてください。スキル一覧が更新されない場合は、新しいセッションでの再確認を案内してください。
```

### English

```text
Install text-shield from [Paste the absolute path to the text-shield folder here] as an Agent Skill for the AI agent I am currently using.
My author name is: [Paste your author name / pen name here]
Read README.md and skills/text-shield/SKILL.md. Prepare the CLI with Python >=3.10,<4.0 using the repository's .venv; create it if needed and run -m pip install . with that environment's Python.
Find this agent's skill discovery directory and install skills/text-shield/ there. If this environment uses a shared skill directory, connect it according to that convention. Report conflicts without deleting or overwriting existing files or links.
Confirm the installed SKILL.md is readable and run the CLI's --version, protect --help, verify --help, and inspect --help. Use a new temporary document to run protect with --author set to the author name above and --poison-level off, then verify with --original, and inspect. Quote the author argument if it contains spaces. Check that the original stays unchanged, the extracted author matches the name above, and both hashes match.
Report the skill location, CLI executable path, and validation results. If the skill list has not refreshed, advise checking in a new session.
```

## Agent Skillとしての使用例

導入後は、対象のファイルを添えて次のように依頼できます。

- 「このMarkdownをプロテクトしてください。元原稿は残してください。」
- 「article.mdに透かしを入れて、article.protected.mdへ保存してください。」
- 「article.protected.mdの署名を検証してください。元原稿はarticle.mdです。」
- 「このテキストの不可視文字を調べてください。」

スキルは置換を指定しない依頼では `--poison-level off` を使い、処理後に元原稿との照合を実行します。CLIを直接呼ぶ場合の既定値は `medium` です。スキルを配置しても一覧に出ない場合は、新しいエージェントセッションで確認してください。

## セットアップ

PowerShellでプロジェクトのディレクトリに移動し、開発用環境を作成してください。

```powershell
cd C:\Projects\text-shield
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pre_commit install
```

実行だけに使う場合は、最後の2行の代わりに `.\.venv\Scripts\python -m pip install .` を実行してください。

## 原稿の処理

```powershell
.\.venv\Scripts\text-shield protect article.md -o article.protected.md --author QuQuLa89 --poison-level off
.\.venv\Scripts\text-shield verify article.protected.md --original article.md
.\.venv\Scripts\text-shield inspect article.protected.md --limit 20
```

`protect` はUTF-8の入力を読み込み、`-o` で指定した新規ファイルに出力します。省略時はUTF-8で標準出力へ書き込みます。Windows PowerShellのリダイレクトによる文字コード変換を避けるため、ファイル保存には `-o` を使ってください。既存ファイルへの出力と、透かしのある原稿への再適用はエラーにします。

`--author` には原稿の著作者名を指定してください。省略すると、環境変数 `TEXT_SHIELD_AUTHOR`、実行場所での `git config user.name` の順に取得します。空または空白だけの環境変数・Git設定は未設定として扱い、どちらからも取得できない場合や `--author` に空白だけを指定した場合は、終了コード `2` で終了します。著作者名の前後の空白は取り除きます。

`--poison-level` の既定値は `medium` です。英字などの置換を避けたい場合は `off` を指定してください。置換率は対象文字ごとの確率で、短い原稿では置換が0件になることもあります。

| 強度     | 対象文字ごとの置換率 |
| -------- | -------------------- |
| `off`    | 0%                   |
| `low`    | 0.5%                 |
| `medium` | 1%                   |
| `high`   | 2%                   |

## 検証と位置表示

`verify` は透かしから著作者名・UTC時刻・元原稿SHA-256・本文SHA-256を抽出します。本文は透かしを除き、オプトアウト宣言とホモグリフ置換を含むUTF-8テキストとして照合します。改行とBOMもハッシュの対象です。入力のBOMは元原稿ハッシュに含め、出力時は非表示リンク定義の解釈を妨げないよう除去します。`--original` を指定すると、処理前の元原稿も照合します。

本文全体が変わった場合、部分コピーした場合、改行や空白が変換された場合は本文ハッシュが一致しません。部分コピーでも完全な透かしが残っていれば、署名を抽出できます。単純な署名文字列だけの透かしも表示できますが、時刻・ハッシュの照合はできません。

終了コードは次のとおりです。

| コード | 意味                                                                        |
| ------ | --------------------------------------------------------------------------- |
| `0`    | 処理成功、または検証対象の全ハッシュが一致しました。                        |
| `1`    | `verify` で透かしなし、照合不一致、または照合情報の不足・破損がありました。 |
| `2`    | 引数、ファイル入出力、UTF-8、Frontmatterなどにエラーがありました。          |

`inspect` はU+200B、U+200C、U+200Dの総数と、置換マップに含まれる同形文字の候補数を表示します。元から使われていた同形文字と今回の置換は区別できないため、「候補」と表示します。位置は0始まりのUnicode文字インデックス、行と列は1始まりです。CRLFは2文字として数えます。

詳細表示は既定で50件までです。`--limit` で上限を指定でき、色は `--color auto|always|never` で切り替えられます。各文字はコードポイントと名前で可視化します。

## 埋め込み方式

オプトアウト宣言は `[//]: # (...)` 形式の参照リンク定義として先頭に挿入します。YAML Frontmatterがある場合はその直後に置きます。Frontmatterの終端が見つからない場合や、既存の `[//]` 参照定義がある場合は、構造の誤認や競合を避けるため処理を中止します。宣言の著作者名と指令名にはURL符号化を使い、改行や括弧によってMarkdownの外へ出ないようにします。

透かしはUTF-8文字列をビット列へ変換し、0をU+200B、1をU+200C、両端をU+200Dで表します。本文の通常行の末尾へ完全な透かしを最大3か所に配置し、Markdownの末尾空白による改行を保ちます。本文に配置できない場合は専用の非表示リンク定義に格納します。CLIの透かし内容は `text-shield:v1:` に続くJSONで、署名のUTF-8サイズに応じてファイル容量が増えます。

ホモグリフ置換と透かし配置では、コードフェンス、インラインコード、インデントしたコード、URL、リンク、参照定義、Frontmatter、HTMLタグ、コメントなどを保守的に除外します。表の行とリンクを含む行の後半も除外するため、通常文でも処理対象が少なくなる場合があります。Markdown方言を完全に解析する仕組みではないため、公開前に利用先のプレビューを確認してください。

## 確認範囲

透かしとオプトアウト宣言は収集や学習を強制的に停止する機能ではありません。トークナイザーへの影響や模倣精度の低下は測定していません。オプトアウト宣言の法的効力も本ツールでは検証していません。

ゼロ幅文字の保持と表示は、フォント・レンダラー・クリップボード・公開サービスに依存します。文字数、改行位置、文字の接合、検索、読み上げに影響する場合があります。ホモグリフも見た目が完全に同一とは限りません。Zenn・Qiita上での表示とコピーの実機検証は未実施です。

ここでの「署名」は著作者名などを埋め込む文字列です。秘密鍵による電子署名や信頼できる時刻認証ではありません。ハッシュの一致は内容の整合を示すもので、著作者や時刻の真正性を証明するものではありません。元原稿と公開時の出力は別途保管してください。

## 開発とテスト

```powershell
.\.venv\Scripts\ruff format .
.\.venv\Scripts\ruff check --fix .
npx --yes prettier@3.6.2 --write README.md skills/text-shield/SKILL.md .pre-commit-config.yaml
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m build
```

pytestではUTF-8署名の復元、CommonMarkのHTML出力との比較、構文の保護、置換確率の境界、改行の保持、CLIの一連の操作、改変検出、既存ファイルの保護を確認します。`markdown-it-py` はテストだけに使います。

pre-commitはPythonのRuff整形・静的解析と、Markdown・JSON・YAMLのPrettier整形を実行します。フック実行時は開発用仮想環境を有効にし、Node.jsとnpmを利用できる状態にしてください。

## ライセンス

ツールのソースコードには [MIT License](LICENSE) を適用します。著作権表記は `Copyright (c) 2026 QuQuLa89` です。処理対象の原稿に対するライセンス指定ではありません。原稿に注入する宣言は `All-Rights-Reserved` です。
