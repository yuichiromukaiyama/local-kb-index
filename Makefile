SHELL := /bin/bash

ROOT ?= .
DB ?= $(ROOT)/.kb_index
Q ?= 検索処理
N ?= 5
SNIPPET ?= 600
CONTENT ?= snippet
PORT ?= 8765
EVAL ?= .kb/eval.yml

.PHONY: help
help:
	@printf '%s\n' 'Local KB command catalog for developers'
	@printf '%s\n' ''
	@printf '%s\n' 'Skill installation:'
	@printf '%s\n' '  make install-personal-skill'
	@printf '%s\n' '  make uninstall-personal-skill'
	@printf '%s\n' '  make install-project-skill ROOT=/path/to/repo'
	@printf '%s\n' '  make uninstall-project-skill ROOT=/path/to/repo'
	@printf '%s\n' ''
	@printf '%s\n' 'KB lifecycle:'
	@printf '%s\n' '  make init ROOT=.'
	@printf '%s\n' '  make index ROOT=.'
	@printf '%s\n' '  make sync ROOT=.'
	@printf '%s\n' '  make rebuild ROOT=.'
	@printf '%s\n' '  make prune ROOT=.'
	@printf '%s\n' '  make watch ROOT=.'
	@printf '%s\n' ''
	@printf '%s\n' 'KB query:'
	@printf '%s\n' '  make query Q="署名付きURL" ROOT=.'
	@printf '%s\n' '  make query-files Q="署名付きURL" ROOT=.'
	@printf '%s\n' '  make query-table Q="署名付きURL" ROOT=.'
	@printf '%s\n' ''
	@printf '%s\n' 'Diagnostics:'
	@printf '%s\n' '  make status ROOT=.'
	@printf '%s\n' '  make doctor ROOT=.'
	@printf '%s\n' '  make eval ROOT=. EVAL=.kb/eval.yml'
	@printf '%s\n' '  make serve ROOT=. PORT=8765'

.PHONY: check
check:
	@./scripts/verify-macos.sh

.PHONY: install-personal-skill
install-personal-skill:
	@./scripts/install-personal-skill.sh

.PHONY: uninstall-personal-skill
uninstall-personal-skill:
	@./scripts/uninstall-personal-skill.sh

.PHONY: install-project-skill
install-project-skill:
	@./scripts/install-project-skill.sh "$(ROOT)"

.PHONY: uninstall-project-skill
uninstall-project-skill:
	@./scripts/uninstall-project-skill.sh "$(ROOT)"

.PHONY: show-skill
show-skill:
	@sed -n '1,240p' skills/local-kb-search/SKILL.md

.PHONY: init
init:
	kb init --root "$(ROOT)"

.PHONY: index
index:
	kb index --root "$(ROOT)" --db "$(DB)" --format json

.PHONY: sync
sync:
	kb sync --root "$(ROOT)" --db "$(DB)" --format json

.PHONY: rebuild
rebuild:
	kb rebuild --root "$(ROOT)" --db "$(DB)" --format json

.PHONY: rebuild-force
rebuild-force:
	kb rebuild --root "$(ROOT)" --db "$(DB)" --force --format json

.PHONY: prune
prune:
	kb prune --root "$(ROOT)" --db "$(DB)" --format json

.PHONY: status
status:
	kb status --root "$(ROOT)" --db "$(DB)" --format json

.PHONY: doctor
doctor:
	kb doctor --root "$(ROOT)" --db "$(DB)" --format json

.PHONY: query
query:
	kb query "$(Q)" --root "$(ROOT)" --db "$(DB)" --mode vector --copilot --content "$(CONTENT)" --max-snippet-chars "$(SNIPPET)" -n "$(N)"

.PHONY: query-files
query-files:
	kb query "$(Q)" --root "$(ROOT)" --db "$(DB)" --mode vector --copilot --content none -n "$(N)"

.PHONY: query-table
query-table:
	kb query "$(Q)" --root "$(ROOT)" --db "$(DB)" --mode vector -n "$(N)"

.PHONY: eval
eval:
	kb eval --root "$(ROOT)" --db "$(DB)" --queries "$(EVAL)" --format json

.PHONY: watch
watch:
	kb watch --root "$(ROOT)" --db "$(DB)"

.PHONY: serve
serve:
	kb serve --root "$(ROOT)" --db "$(DB)" --port "$(PORT)"

.PHONY: skill-query
skill-query:
	@skills/local-kb-search/scripts/kb-search.sh "$(Q)" "$(ROOT)" "$(N)" "$(SNIPPET)" "$(CONTENT)"

.PHONY: skill-query-files
skill-query-files:
	@skills/local-kb-search/scripts/kb-search-files.sh "$(Q)" "$(ROOT)" "$(N)"

.PHONY: zip
zip:
	@rm -f ../local-kb-copilot-skill.zip
	@cd .. && zip -qr local-kb-copilot-skill.zip local-kb-copilot-skill -x 'local-kb-copilot-skill/.git/*'
	@printf 'Wrote ../local-kb-copilot-skill.zip\n'
