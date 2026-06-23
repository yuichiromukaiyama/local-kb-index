# Local KB Copilot Skill

Use your local vector-search knowledge base from GitHub Copilot CLI — without MCP.

`local-kb-copilot-skill` is an Agent Skill package that teaches GitHub Copilot CLI how to use a local `kb` command for repository-aware semantic search.

It is designed for teams and individual developers who want:

- local semantic search over a repository
- Copilot CLI integration without MCP
- compact AI-friendly search output
- controlled read-only behavior by default
- a simple command catalog for operating the KB index

The skill assumes that the `kb` command is already installed and available on `PATH`.

## What this is

This repository does not implement the vector search engine itself.  
Instead, it provides:

- a GitHub Copilot CLI Agent Skill
- shell wrapper scripts for the `kb` command
- install / uninstall scripts for personal and project skills
- a developer-oriented `Makefile`
- documentation for local KB search workflows

The actual search is delegated to your local `kb` CLI.

```text
GitHub Copilot CLI
  ↓
Agent Skill: local-kb-search
  ↓
Shell wrapper scripts
  ↓
kb command
  ↓
Local vector index: .kb_index
````

## Why this exists

GitHub Copilot CLI can execute shell commands, but it does not automatically know that your local `kb` command is the preferred way to search your repository.

This skill gives Copilot CLI a stable operating procedure:

* use `kb query` before broad codebase investigation
* prefer local vector search for repository discovery
* return compact AI-oriented output to reduce token usage
* avoid noisy table output when search results are consumed by AI
* avoid index mutation commands unless explicitly requested
* use local `.kb_index` data only

This is useful when your organization does not allow MCP, or when you want retrieval to remain local and auditable.

## Main use cases

### 1. Copilot CLI repository investigation

Use this when you want Copilot CLI to search the local codebase before answering implementation or design questions.

Example prompt:

```text
このリポジトリでファイルアップロードのSAS発行処理がどこにあるか、local KB search を使って調査してください。
```

Expected behavior:

```text
Copilot CLI
  → uses the local-kb-search skill
  → runs kb query through the wrapper script
  → reads compact search results
  → inspects relevant files
  → answers with grounded file references
```

### 2. Simple semantic search from the terminal

You can also use the same `kb` command directly as a simple semantic search tool.

For example:

```bash
kb query "署名付きURLの発行処理" --root . --db ./.kb_index --mode vector -n 5
```

This is useful when you want to quickly find related files, functions, design documents, or implementation notes without asking Copilot.

AI-oriented compact output:

```bash
kb query "署名付きURLの発行処理" \
  --root . \
  --db ./.kb_index \
  --mode vector \
  --copilot \
  --content snippet \
  --max-snippet-chars 600 \
  -n 5
```

File candidates only:

```bash
kb query "署名付きURLの発行処理" \
  --root . \
  --db ./.kb_index \
  --mode vector \
  --copilot \
  --content none \
  -n 8
```

### 3. Codebase impact analysis

Use KB search before changing shared APIs, domain models, database schemas, file upload flows, authentication logic, or configuration structures.

Example:

```text
runtime_config の保存仕様を変更した場合の影響範囲を、local KB search を使って調査してください。
```

### 4. Design document lookup

Use vector search when exact keywords are unknown.

Example:

```bash
kb query "チャット履歴の保存と検索インデックス" --root . --db ./.kb_index --mode vector -n 5
```

This can find semantically related documents even when the wording differs from the query.

## Features

* GitHub Copilot CLI Agent Skill for local KB search
* macOS-focused install and verification scripts
* Personal skill installation under `~/.copilot/skills`
* Project skill installation under `.github/skills`
* Wrapper scripts for common `kb` operations
* Developer-oriented Makefile command catalog
* Compact AI-facing query output
* Direct terminal semantic search support
* Read-oriented default behavior
* Explicit safety policy for index mutation commands
* No MCP dependency

## Repository layout

```text
local-kb-copilot-skill/
├── Makefile
├── README.md
├── scripts/
│   ├── install-personal-skill.sh
│   ├── install-project-skill.sh
│   ├── uninstall-personal-skill.sh
│   ├── uninstall-project-skill.sh
│   └── verify-macos.sh
└── skills/
    └── local-kb-search/
        ├── SKILL.md
        └── scripts/
            ├── common.sh
            ├── kb-doctor.sh
            ├── kb-index.sh
            ├── kb-init.sh
            ├── kb-rebuild.sh
            ├── kb-search-files.sh
            ├── kb-search.sh
            ├── kb-status.sh
            └── kb-sync.sh
```

## Requirements

* macOS
* GitHub Copilot CLI
* `bash`
* `make`
* `kb` installed and available on `PATH`
* A repository with a local KB index, usually at `.kb_index`

Check your environment:

```bash
make check
```

Verify that `kb` is available:

```bash
command -v kb
kb doctor --root . --db ./.kb_index
```

## Quick start

Clone or extract this repository, then install the skill as a personal skill:

```bash
make install-personal-skill
```

This installs the skill to:

```text
~/.copilot/skills/local-kb-search
```

Then open a repository that already has a KB index and use Copilot CLI normally.

You can test the same behavior manually:

```bash
make query ROOT=/path/to/repo Q="署名付きURL SAS upload session" N=5
```

## Install as a personal skill

Use this when you want the skill to be available across repositories.

```bash
make install-personal-skill
```

Installed location:

```text
~/.copilot/skills/local-kb-search
```

Uninstall:

```bash
make uninstall-personal-skill
```

## Install as a project skill

Use this when you want the skill to be available from a specific repository.

```bash
make install-project-skill ROOT=/path/to/repo
```

Installed location:

```text
/path/to/repo/.github/skills/local-kb-search
```

Uninstall:

```bash
make uninstall-project-skill ROOT=/path/to/repo
```

## Prepare a repository index

In the target repository:

```bash
cd /path/to/repo
kb init --root .
kb index --root . --db ./.kb_index
```

After code or document changes:

```bash
kb sync --root . --db ./.kb_index
```

Check status:

```bash
kb status --root . --db ./.kb_index
```

Diagnose problems:

```bash
kb doctor --root . --db ./.kb_index
```

## How Copilot is expected to use it

The skill tells Copilot CLI to use compact vector search for repository investigation:

```bash
kb query "<query>" \
  --root . \
  --db ./.kb_index \
  --mode vector \
  --copilot \
  --content snippet \
  --max-snippet-chars 600 \
  -n 5
```

The equivalent wrapper script is:

```bash
~/.copilot/skills/local-kb-search/scripts/kb-search.sh "<query>" . 5 600 snippet
```

For file candidates only, without snippets:

```bash
~/.copilot/skills/local-kb-search/scripts/kb-search-files.sh "<query>" . 8
```

## Direct semantic search examples

Human-readable table output:

```bash
make query-table ROOT=/path/to/repo Q="検索処理" N=5
```

Compact AI-oriented output:

```bash
make query ROOT=/path/to/repo Q="検索処理" N=5 SNIPPET=600
```

File candidates only:

```bash
make query-files ROOT=/path/to/repo Q="検索処理" N=8
```

Direct `kb` command:

```bash
kb query "検索処理" --root /path/to/repo --db /path/to/repo/.kb_index --mode vector -n 5
```

## Developer command catalog

The `Makefile` is a command catalog for developers and operators. It is not required by the Agent Skill at runtime.

Common commands:

```bash
make help
make check
make status ROOT=/path/to/repo
make doctor ROOT=/path/to/repo
make query ROOT=/path/to/repo Q="署名付きURL SAS upload session" N=5 SNIPPET=600
make query-files ROOT=/path/to/repo Q="runtime_config model response detail" N=8
make query-table ROOT=/path/to/repo Q="検索処理" N=5
make sync ROOT=/path/to/repo
```

Packaging:

```bash
make zip
```

Remove generated zip:

```bash
make clean-zip
```

## Command behavior

| Command                                         | Purpose                                     | Typical user                     |
| ----------------------------------------------- | ------------------------------------------- | -------------------------------- |
| `make install-personal-skill`                   | Install the skill under `~/.copilot/skills` | User                             |
| `make install-project-skill ROOT=/path/to/repo` | Install the skill into a repository         | Maintainer                       |
| `make query`                                    | Run compact AI-oriented semantic search     | Developer / Agent behavior check |
| `make query-files`                              | Return file candidates only                 | Developer / Agent behavior check |
| `make query-table`                              | Human-readable semantic search output       | Developer                        |
| `make status`                                   | Show index status                           | Developer                        |
| `make doctor`                                   | Diagnose environment and index health       | Developer                        |
| `make sync`                                     | Update changed files in the index           | Developer                        |
| `make zip`                                      | Create a distributable archive              | Maintainer                       |

## Safety policy

The skill is intentionally conservative.

The agent may use read-oriented commands for search and diagnostics:

* `kb query`
* `kb status`
* `kb doctor`

The agent must not run index mutation commands unless the user explicitly asks:

* `kb sync`
* `kb index`
* `kb rebuild`
* `kb rebuild --force`
* `kb prune`

The reason is operational safety. Index mutation can be expensive, can change local state, and may consume CPU, disk, or embedding resources.

## What this does not do

This package does not:

* install the `kb` command
* create embeddings by itself
* provide a VS Code extension
* provide an MCP server
* send code to a remote service
* automatically rebuild `.kb_index`
* make Copilot CLI a native tool host

It only provides Agent Skill instructions and shell wrappers so Copilot CLI can use an already-installed local KB command in a disciplined way.

## Personal skill vs project skill

Use a personal skill when you want the same behavior across repositories:

```text
~/.copilot/skills/local-kb-search
```

Use a project skill when you want a repository to carry its own skill definition:

```text
.github/skills/local-kb-search
```

A project skill is useful when a team wants consistent behavior for one codebase. A personal skill is better for individual workflows.

## Troubleshooting

### `kb command was not found in PATH`

Install the KB application first, then confirm:

```bash
command -v kb
kb --help
```

### The skill is installed but Copilot CLI does not appear to use it

Check that `SKILL.md` exists in the expected location:

```bash
ls -la ~/.copilot/skills/local-kb-search
cat ~/.copilot/skills/local-kb-search/SKILL.md
```

For project skill:

```bash
ls -la .github/skills/local-kb-search
cat .github/skills/local-kb-search/SKILL.md
```

### Search returns stale results

Update the local index:

```bash
kb sync --root . --db ./.kb_index
```

If the index is broken or incompatible:

```bash
kb rebuild --root . --db ./.kb_index
```

Use force only when you intentionally want to recreate the index:

```bash
kb rebuild --root . --db ./.kb_index --force
```

### Search output is too large

Use file-only output:

```bash
make query-files ROOT=. Q="検索処理" N=5
```

Or reduce snippet size:

```bash
make query ROOT=. Q="検索処理" SNIPPET=300 N=3
```

## Example prompts for Copilot CLI

Ask Copilot CLI to investigate with local KB:

```text
このリポジトリでファイルアップロードのSAS発行処理がどこにあるか、local KB search を使って調査してください。
```

Ask for impact analysis:

```text
runtime_config の保存仕様を変更した場合の影響範囲を、local KB search を使って調査してください。
```

Ask for candidates only:

```text
まず local KB search で関連ファイル候補だけを出してください。本文は不要です。
```

Ask for simple semantic search:

```text
local KB search を使って「認証前のアップロード制御」に関連するファイルを探してください。
```

## Design principles

* Local-first retrieval
* Simple semantic search from the terminal
* Copilot CLI integration without MCP
* Compact output for AI consumption
* Human-readable commands for developers
* Read-oriented default behavior
* Explicit user consent for index mutation
* macOS-focused operational simplicity
