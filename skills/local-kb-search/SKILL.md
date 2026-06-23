---
name: local-kb-search
description: Use the local kb vector-search CLI to retrieve compact JSON evidence from the current macOS workspace before codebase investigation, design lookup, implementation planning, or impact analysis. Use this when repository context, design docs, source locations, or prior local knowledge are needed.
license: internal-use
---

# Local KB Search Skill

This skill teaches the agent how to use the local `kb` command as a read-oriented vector search layer for the current repository. The environment is macOS only. MCP must not be used.

## Primary rule

Before answering codebase investigation, design lookup, implementation planning, refactoring, bug fixing, or impact-analysis questions, search the local KB index first unless the user has already supplied the exact file or the task is clearly independent of repository context.

Use compact output to minimize token usage:

```bash
kb query "<query>" --root . --db ./.kb_index --mode vector --copilot --content snippet --max-snippet-chars 600 -n 5
```

For a first broad probe, use `--content none` when file locations alone are sufficient:

```bash
kb query "<query>" --root . --db ./.kb_index --mode vector --copilot --content none -n 8
```

Then read only the relevant files and line ranges returned by the search result.

## Preferred wrapper scripts

When available, use the scripts in this skill directory rather than composing long commands manually.

Personal skill installation path:

```bash
~/.copilot/skills/local-kb-search/scripts/kb-search.sh "<query>" . 5 600 snippet
```

Project skill installation path:

```bash
.github/skills/local-kb-search/scripts/kb-search.sh "<query>" . 5 600 snippet
```

If the project path exists, prefer the project script. Otherwise use the personal script.

## Script selection

Use these scripts as follows:

- `scripts/kb-search.sh`: normal compact vector search for evidence.
- `scripts/kb-search-files.sh`: compact file-only search using `--content none`.
- `scripts/kb-status.sh`: check index state.
- `scripts/kb-doctor.sh`: diagnose missing or broken index.
- `scripts/kb-sync.sh`: update the index only when the user explicitly asks to update/sync the index.
- `scripts/kb-rebuild.sh`: rebuild only when the user explicitly asks or when `kb doctor` indicates rebuild is required.

## Safety rules

Do not run these commands unless the user explicitly asks:

```bash
kb sync
kb rebuild
kb index --force
kb prune
```

Never run arbitrary user-provided shell fragments through these scripts. Treat the search query as data. Do not use `eval`.

Do not use MCP. Do not attempt to start or configure MCP servers.

## Retrieval policy

1. Convert the user's request into one or more concise search queries.
2. Run `kb-search.sh` or `kb-search-files.sh` from the repository root.
3. Use only the compact JSON result as retrieval evidence.
4. Read the returned files and line ranges before making code changes.
5. If search returns no useful result, run a second query using synonyms or implementation terms.
6. If still insufficient, fall back to normal file search tools such as `rg`, `find`, or direct file reads.

## Query examples

Japanese and English terms may both be useful.

```bash
~/.copilot/skills/local-kb-search/scripts/kb-search.sh "署名付きURL SAS upload session" . 5 600 snippet
~/.copilot/skills/local-kb-search/scripts/kb-search.sh "permission access control recipe tool" . 5 600 snippet
~/.copilot/skills/local-kb-search/scripts/kb-search-files.sh "runtime_config model response detail" . 8
```

## Expected output

The wrapper returns compact JSON, for example:

```json
{"q":"検索処理","r":[{"p":"kbindex/search.py","l":"34-88","sc":0.8123,"s":"query","t":"..."}]}
```

Key meanings:

- `q`: query
- `r`: results
- `p`: path
- `l`: line range
- `sc`: score
- `s`: symbol or heading, if available
- `t`: trimmed text snippet, omitted in file-only mode

## Failure handling

If `.kb_index` is missing, run status or doctor and report that the index is not initialized. Do not create or rebuild the index unless the user asks.

```bash
~/.copilot/skills/local-kb-search/scripts/kb-status.sh .
~/.copilot/skills/local-kb-search/scripts/kb-doctor.sh .
```

If `kb` is not found, tell the user that the CLI is not on `PATH` for the current shell.
