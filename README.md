# Local KB Copilot Skill

This repository contains a GitHub Copilot CLI agent skill for using the local `kb` vector-search command from macOS.

The skill does not use MCP. It assumes the `kb` command is already installed and available on `PATH`.

## Contents

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

## Install as a personal skill

```bash
make install-personal-skill
```

This installs the skill to:

```text
~/.copilot/skills/local-kb-search
```

## Install as a project skill

```bash
make install-project-skill ROOT=/path/to/repo
```

This installs the skill to:

```text
/path/to/repo/.github/skills/local-kb-search
```

## Uninstall

```bash
make uninstall-personal-skill
make uninstall-project-skill ROOT=/path/to/repo
```

## Developer command catalog

The Makefile is a command catalog for the KB application developer. It is not required by the agent skill at runtime.

Examples:

```bash
make status ROOT=/path/to/repo
make doctor ROOT=/path/to/repo
make query ROOT=/path/to/repo Q="署名付きURL SAS upload session" N=5 SNIPPET=600
make query-files ROOT=/path/to/repo Q="runtime_config model response detail" N=8
make sync ROOT=/path/to/repo
```

## Agent-facing behavior

The skill instructs Copilot CLI to use compact vector search output:

```bash
kb query "<query>" --root . --db ./.kb_index --mode vector --copilot --content snippet --max-snippet-chars 600 -n 5
```

The wrapper script equivalent is:

```bash
~/.copilot/skills/local-kb-search/scripts/kb-search.sh "<query>" . 5 600 snippet
```

## Safety policy

The skill tells the agent not to run update commands unless the user explicitly asks:

- `kb sync`
- `kb rebuild`
- `kb index --force`
- `kb prune`

Search and diagnostics are read-oriented and are safe for normal use.
