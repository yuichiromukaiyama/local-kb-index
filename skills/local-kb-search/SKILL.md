---
name: local-kb-search
description: Use the local kb vector-search command for repository semantic search from GitHub Copilot CLI, with optional repo-relative path filters. No MCP is required.
---

# Local KB Search

Use this skill when a task requires repository-aware semantic search, codebase investigation, impact analysis, design-document lookup, or simple local semantic search using the `kb` command.

The local `kb` CLI must already be installed and available on `PATH`. This skill does not install `kb`, does not create embeddings by itself, and does not use MCP.

## Default search behavior

When investigating the repository, prefer local vector search before broad manual inspection.

Default command form:

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

The output is compact and intended for AI consumption.

## Wrapper scripts

When using the bundled wrapper scripts, prefer these forms.

Search with snippets:

```bash
./skills/local-kb-search/scripts/kb-search.sh "<query>" . 5 600 snippet
```

Search file candidates only:

```bash
./skills/local-kb-search/scripts/kb-search-files.sh "<query>" . 8
```

If the skill is installed as a personal skill, the scripts are usually available at:

```text
~/.copilot/skills/local-kb-search/scripts/
```

If the skill is installed as a project skill, the scripts are usually available at:

```text
.github/skills/local-kb-search/scripts/
```

If the script path is unclear, use `kb query` directly.

## Path-filtered search

Use path filters when the user asks to search within a specific directory, submodule, documentation area, source tree, or file family.

Examples of user intent that should trigger path filtering:

- "Search only under src"
- "Limit this to docs/spec"
- "Look in backend only"
- "Do not include tests"
- "Find this in app/api but exclude generated files"

Direct `kb query` path filter examples:

```bash
kb query "<query>" --root . --db ./.kb_index --mode vector --path "src" -n 5
```

```bash
kb query "<query>" --root . --db ./.kb_index --mode vector --include "docs/spec/**" -n 5
```

```bash
kb query "<query>" \
  --root . \
  --db ./.kb_index \
  --mode vector \
  --include "src/**" \
  --exclude "**/tests/**" \
  --copilot \
  --content snippet \
  --max-snippet-chars 600 \
  -n 5
```

Wrapper path filter examples:

```bash
./skills/local-kb-search/scripts/kb-search.sh "<query>" . 5 600 snippet "src" "" ""
```

```bash
./skills/local-kb-search/scripts/kb-search.sh "<query>" . 5 600 snippet "" "docs/spec/**" ""
```

```bash
./skills/local-kb-search/scripts/kb-search.sh "<query>" . 5 600 snippet "" "src/**,docs/spec/**" "**/tests/**"
```

File-candidate-only path filter:

```bash
./skills/local-kb-search/scripts/kb-search-files.sh "<query>" . 8 "src" "" ""
```

## Path filter rules

Treat path filter values as repository-relative paths or globs.

- `--path "src"` means `src` and files under `src/`.
- `--include "src/**"` includes files under `src`.
- `--include "docs/spec/**"` includes design/spec documents.
- `--exclude "**/tests/**"` excludes test directories.
- Use multiple includes or excludes when the user names multiple areas.

Do not change `--root` to a subdirectory only to filter results. Keep `--root .` for the repository root and use `--path`, `--include`, or `--exclude` for narrowing search scope.

## Search result handling

After search:

1. Read the compact search results.
2. Prefer the highest-scoring relevant file candidates.
3. Inspect the actual files before making code changes.
4. State when search results are insufficient or ambiguous.
5. Use additional shell search only when local KB results are insufficient.

For token efficiency, use file-candidate-only output first when the user asks for a broad search or when many results are likely:

```bash
kb query "<query>" --root . --db ./.kb_index --mode vector --copilot --content none -n 8
```

Then retrieve snippets for narrower follow-up searches.

## Safety policy

Read-oriented commands are safe for normal use:

- `kb query`
- `kb status`
- `kb doctor`

Do not run index mutation commands unless the user explicitly asks:

- `kb sync`
- `kb index`
- `kb rebuild`
- `kb rebuild --force`
- `kb prune`

If search results seem stale, tell the user that the index may need `kb sync`. Do not run `kb sync` automatically unless the user explicitly asks for index update.

## Preferred query strategy

Use natural-language and code-aware search phrases. Include domain terms, likely identifiers, and bilingual terms when helpful.

Examples:

```text
SAS upload session signed URL
runtime_config model response detail
thread message search index
permission resource_type principal_type
```

For Japanese repositories or Japanese design docs, Japanese queries are acceptable:

```text
署名付きURL 発行処理
ファイルアップロード 完了検証
権限チェック principal_type
```

## Failure handling

If `kb` is missing:

```bash
command -v kb
```

If index is missing or unhealthy:

```bash
kb status --root . --db ./.kb_index
kb doctor --root . --db ./.kb_index
```

Report the problem and ask the user whether to initialize, sync, or rebuild the index. Do not perform mutation commands without explicit permission.
