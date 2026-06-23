```makefile id="0v3bt9"
SHELL := /bin/bash

# --------------------------------------------------------------------
# Local KB Copilot Skill / KB command catalog
#
# この Makefile は KB コマンド開発者・運用者向けのコマンド集です。
# Agent Skill が実行時に直接この Makefile を使う想定ではありません。
# 主要な kb コマンド、skill のインストール、動作確認、配布 zip 作成を
# 1つの入口から実行できるようにしています。
# --------------------------------------------------------------------

ROOT ?= .
DB ?= $(ROOT)/.kb_index

Q ?= 検索処理
N ?= 5
SNIPPET ?= 600
CONTENT ?= snippet
PORT ?= 8765
EVAL ?= .kb/eval.yml

SKILL_NAME := local-kb-search
SKILL_SRC := skills/$(SKILL_NAME)
PERSONAL_SKILL_DIR := $(HOME)/.copilot/skills/$(SKILL_NAME)
PROJECT_SKILL_DIR := $(ROOT)/.github/skills/$(SKILL_NAME)

ZIP_NAME ?= local-kb-copilot-skill.zip
ZIP_OUT ?= ./$(ZIP_NAME)

.DEFAULT_GOAL := help

# ヘルプを表示します。
# 使える make target、主要変数、利用例を一覧表示します。
.PHONY: help
help:
	@printf '%s\n' 'Local KB command catalog for developers'
	@printf '%s\n' ''
	@printf '%s\n' 'Variables:'
	@printf '%s\n' '  ROOT=.                  Target repository root'
	@printf '%s\n' '  DB=$$(ROOT)/.kb_index    KB index path'
	@printf '%s\n' '  Q="検索処理"             Query text'
	@printf '%s\n' '  N=5                     Number of results'
	@printf '%s\n' '  SNIPPET=600             Max snippet chars for AI-oriented output'
	@printf '%s\n' '  CONTENT=snippet         snippet | none'
	@printf '%s\n' '  PORT=8765               kb serve port'
	@printf '%s\n' '  EVAL=.kb/eval.yml       Evaluation query file'
	@printf '%s\n' ''
	@printf '%s\n' 'Skill installation:'
	@printf '%s\n' '  make install-personal-skill'
	@printf '%s\n' '  make uninstall-personal-skill'
	@printf '%s\n' '  make install-project-skill ROOT=/path/to/repo'
	@printf '%s\n' '  make uninstall-project-skill ROOT=/path/to/repo'
	@printf '%s\n' '  make show-skill'
	@printf '%s\n' ''
	@printf '%s\n' 'KB lifecycle:'
	@printf '%s\n' '  make init ROOT=.'
	@printf '%s\n' '  make index ROOT=.'
	@printf '%s\n' '  make sync ROOT=.'
	@printf '%s\n' '  make rebuild ROOT=.'
	@printf '%s\n' '  make rebuild-force ROOT=.'
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
	@printf '%s\n' '  make status-json ROOT=.'
	@printf '%s\n' '  make doctor ROOT=.'
	@printf '%s\n' '  make doctor-json ROOT=.'
	@printf '%s\n' '  make eval ROOT=. EVAL=.kb/eval.yml'
	@printf '%s\n' '  make serve ROOT=. PORT=8765'
	@printf '%s\n' ''
	@printf '%s\n' 'Skill wrapper checks:'
	@printf '%s\n' '  make skill-query Q="署名付きURL" ROOT=.'
	@printf '%s\n' '  make skill-query-files Q="署名付きURL" ROOT=.'
	@printf '%s\n' '  make skill-status ROOT=.'
	@printf '%s\n' '  make skill-doctor ROOT=.'
	@printf '%s\n' ''
	@printf '%s\n' 'Packaging:'
	@printf '%s\n' '  make zip'
	@printf '%s\n' '  make clean-zip'

# --------------------------------------------------------------------
# Internal guards
# --------------------------------------------------------------------

# kb コマンドが PATH 上に存在するか確認します。
# 存在しない場合は、以降の kb 操作を実行せずエラーで停止します。
.PHONY: require-kb
require-kb:
	@command -v kb >/dev/null 2>&1 || { \
		printf '%s\n' 'ERROR: kb command was not found in PATH.' >&2; \
		printf '%s\n' 'Install local-kb-production first, then retry.' >&2; \
		exit 127; \
	}

# Agent Skill の SKILL.md が存在するか確認します。
# skill 配布物の欠落やディレクトリ構成ミスを早期に検出します。
.PHONY: require-skill
require-skill:
	@test -f "$(SKILL_SRC)/SKILL.md" || { \
		printf 'ERROR: missing skill file: %s\n' "$(SKILL_SRC)/SKILL.md" >&2; \
		exit 1; \
	}

# macOS 前提の実行環境を確認します。
# scripts/verify-macos.sh により OS、必須コマンド、kb の存在などを検査します。
.PHONY: check
check:
	@./scripts/verify-macos.sh

# --------------------------------------------------------------------
# Skill installation
# --------------------------------------------------------------------

# 個人用 Agent Skill として local-kb-search をインストールします。
# インストール先は ~/.copilot/skills/local-kb-search です。
# 複数リポジトリで共通利用したい場合はこちらを使います。
.PHONY: install-personal-skill
install-personal-skill: require-skill
	@./scripts/install-personal-skill.sh
	@printf 'Installed personal skill: %s\n' "$(PERSONAL_SKILL_DIR)"

# 個人用 Agent Skill を削除します。
# 削除対象は ~/.copilot/skills/local-kb-search です。
.PHONY: uninstall-personal-skill
uninstall-personal-skill:
	@./scripts/uninstall-personal-skill.sh
	@printf 'Removed personal skill: %s\n' "$(PERSONAL_SKILL_DIR)"

# 指定したリポジトリに project skill として local-kb-search をインストールします。
# インストール先は $(ROOT)/.github/skills/local-kb-search です。
# リポジトリ固有の運用ルールとして共有したい場合に使います。
.PHONY: install-project-skill
install-project-skill: require-skill
	@./scripts/install-project-skill.sh "$(ROOT)"
	@printf 'Installed project skill: %s\n' "$(PROJECT_SKILL_DIR)"

# 指定したリポジトリから project skill を削除します。
# 削除対象は $(ROOT)/.github/skills/local-kb-search です。
.PHONY: uninstall-project-skill
uninstall-project-skill:
	@./scripts/uninstall-project-skill.sh "$(ROOT)"
	@printf 'Removed project skill: %s\n' "$(PROJECT_SKILL_DIR)"

# 同梱している SKILL.md の内容を表示します。
# Copilot CLI に渡す指示内容を確認するための閲覧用 target です。
.PHONY: show-skill
show-skill: require-skill
	@sed -n '1,260p' "$(SKILL_SRC)/SKILL.md"

# --------------------------------------------------------------------
# KB lifecycle
#
# これらは KB index の作成・更新・再構築・監視を行う操作です。
# 開発者・運用者が手動で使う想定のため、通常は人間向け出力にしています。
# Agent / Copilot に渡す必要があるものだけ別 target で JSON 化します。
# --------------------------------------------------------------------

# 対象リポジトリに KB 設定ファイルを初期作成します。
# 通常は .kb/config.yml や .kbignore の生成に使います。
.PHONY: init
init: require-kb
	kb init --root "$(ROOT)"

# 対象リポジトリ全体を初回 index します。
# 既存 index がない場合、または明示的に全体作成したい場合に使います。
# 通常の運用更新では sync を使います。
.PHONY: index
index: require-kb
	kb index --root "$(ROOT)" --db "$(DB)"

# 対象リポジトリの差分 index を実行します。
# 未変更ファイルはスキップし、新規・変更・削除分だけを反映する想定です。
# 日常運用では index よりこちらを使います。
.PHONY: sync
sync: require-kb
	kb sync --root "$(ROOT)" --db "$(DB)"

# index の再構築を行います。
# スキーマ不整合、検索品質の劣化、モデル変更後の再作成などに使います。
# force なしのため、実装側の安全確認が入る想定です。
.PHONY: rebuild
rebuild: require-kb
	kb rebuild --root "$(ROOT)" --db "$(DB)"

# index を強制的に再構築します。
# 既存 index を作り直す可能性があるため、通常運用では慎重に使います。
.PHONY: rebuild-force
rebuild-force: require-kb
	kb rebuild --root "$(ROOT)" --db "$(DB)" --force

# 削除済みファイル、古い chunk、不要なメタデータなどを掃除します。
# index サイズが増えた場合や sync 後の整理に使います。
.PHONY: prune
prune: require-kb
	kb prune --root "$(ROOT)" --db "$(DB)"

# ファイル変更を監視し、変更に応じて index 更新します。
# 長時間実行される foreground プロセスです。
.PHONY: watch
watch: require-kb
	kb watch --root "$(ROOT)" --db "$(DB)"

# --------------------------------------------------------------------
# KB query
#
# query       : Copilot / AI 向けの compact 出力
# query-files : 本文なしでファイル・行範囲候補だけ返す省トークン出力
# query-table : 人間がターミナルで読むためのテーブル出力
# --------------------------------------------------------------------

# Copilot / AI に渡す前提の compact 検索を実行します。
# snippet を含めますが、SNIPPET 文字数で切り詰めます。
# 通常、Agent Skill から使わせる検索形式に最も近い target です。
.PHONY: query
query: require-kb
	kb query "$(Q)" \
		--root "$(ROOT)" \
		--db "$(DB)" \
		--mode vector \
		--copilot \
		--content "$(CONTENT)" \
		--max-snippet-chars "$(SNIPPET)" \
		-n "$(N)"

# Copilot / AI 向けに、本文なしで検索結果候補だけを返します。
# path、line range、score など最小情報に絞りたい場合に使います。
.PHONY: query-files
query-files: require-kb
	kb query "$(Q)" \
		--root "$(ROOT)" \
		--db "$(DB)" \
		--mode vector \
		--copilot \
		--content none \
		-n "$(N)"

# 人間が読むための通常テーブル形式で検索します。
# デバッグや検索品質確認で使います。
.PHONY: query-table
query-table: require-kb
	kb query "$(Q)" \
		--root "$(ROOT)" \
		--db "$(DB)" \
		--mode vector \
		-n "$(N)"

# --------------------------------------------------------------------
# Diagnostics
# --------------------------------------------------------------------

# index の状態を人間向けに表示します。
# indexed file 数、変更検出、モデル、最終更新時刻などの確認に使います。
.PHONY: status
status: require-kb
	kb status --root "$(ROOT)" --db "$(DB)"

# index の状態を JSON で表示します。
# CI、hook、外部スクリプトから機械判定したい場合に使います。
.PHONY: status-json
status-json: require-kb
	kb status --root "$(ROOT)" --db "$(DB)" --format json

# kb の動作環境と index の健全性を人間向けに診断します。
# モデル、DB、スキーマ、ベクトル列、依存関係などの確認に使います。
.PHONY: doctor
doctor: require-kb
	kb doctor --root "$(ROOT)" --db "$(DB)"

# kb の診断結果を JSON で表示します。
# CI や自動診断スクリプトから扱う場合に使います。
.PHONY: doctor-json
doctor-json: require-kb
	kb doctor --root "$(ROOT)" --db "$(DB)" --format json

# 検索品質評価を実行します。
# .kb/eval.yml 等に定義した query / expected result を使って評価します。
.PHONY: eval
eval: require-kb
	kb eval --root "$(ROOT)" --db "$(DB)" --queries "$(EVAL)" --format json

# kb のローカル HTTP サーバーを起動します。
# VS Code 拡張や外部ツールから HTTP 経由で検索したい場合に使います。
.PHONY: serve
serve: require-kb
	kb serve --root "$(ROOT)" --db "$(DB)" --port "$(PORT)"

# --------------------------------------------------------------------
# Agent Skill wrapper checks
#
# これらは Agent Skill に同梱している shell wrapper の動作確認用です。
# Copilot CLI が最終的に呼び出す可能性のあるスクリプトを、
# 人間が手元で検証するために用意しています。
# --------------------------------------------------------------------

# Agent Skill 用の kb-search.sh を通して検索します。
# Skill 経由で想定通り compact 出力になるか確認するための target です。
.PHONY: skill-query
skill-query: require-skill
	@"$(SKILL_SRC)/scripts/kb-search.sh" "$(Q)" "$(ROOT)" "$(N)" "$(SNIPPET)" "$(CONTENT)"

# Agent Skill 用の kb-search-files.sh を通して検索します。
# 本文なしのファイル候補だけが返るか確認します。
.PHONY: skill-query-files
skill-query-files: require-skill
	@"$(SKILL_SRC)/scripts/kb-search-files.sh" "$(Q)" "$(ROOT)" "$(N)"

# Agent Skill 用の kb-status.sh を通して index 状態を確認します。
# Skill 側から status を確認する挙動の検証に使います。
.PHONY: skill-status
skill-status: require-skill
	@"$(SKILL_SRC)/scripts/kb-status.sh" "$(ROOT)"

# Agent Skill 用の kb-doctor.sh を通して診断します。
# Skill 側から環境診断できるか確認するための target です。
.PHONY: skill-doctor
skill-doctor: require-skill
	@"$(SKILL_SRC)/scripts/kb-doctor.sh" "$(ROOT)"

# Agent Skill 用の kb-sync.sh を通して差分更新します。
# 原則、Copilot が勝手に実行する用途ではなく、人間が明示確認するための検証用です。
.PHONY: skill-sync
skill-sync: require-skill
	@"$(SKILL_SRC)/scripts/kb-sync.sh" "$(ROOT)"

# --------------------------------------------------------------------
# Packaging
# --------------------------------------------------------------------

# 作成済みの配布 zip を削除します。
# 再パッケージ前の掃除に使います。
.PHONY: clean-zip
clean-zip:
	@rm -f "$(ZIP_OUT)"
	@printf 'Removed %s\n' "$(ZIP_OUT)"

# この skill 配布リポジトリを zip 化します。
# .git や .DS_Store は除外します。
# 既定では ./local-kb-copilot-skill.zip を作成します。
.PHONY: zip
zip:
	@rm -f "$(ZIP_OUT)"
	@base_dir="$$(basename "$$(pwd)")"; \
	parent_dir="$$(dirname "$$(pwd)")"; \
	zip_path="$$(cd "$$(dirname "$(ZIP_OUT)")" && pwd)/$$(basename "$(ZIP_OUT)")"; \
	cd "$$parent_dir" && zip -qr "$$zip_path" "$$base_dir" \
		-x "$$base_dir/.git/*" \
		-x "$$base_dir/.DS_Store" \
		-x "$$base_dir/**/.DS_Store" \
		-x "$$base_dir/$(ZIP_NAME)"
	@printf 'Wrote %s\n' "$(ZIP_OUT)"
```
