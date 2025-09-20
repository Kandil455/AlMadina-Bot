PY=python3

.PHONY: hydrate-glossary
hydrate-glossary:
	$(PY) scripts/hydrate_glossary.py --append

.PHONY: compile
compile:
	$(PY) -m compileall ai_services.py handlers/common_handlers.py handlers/main_handler.py telegraph_utils.py file_generator.py keyboards.py database.py medical_glossary.py

.PHONY: push
push:
	@git rev-parse --is-inside-work-tree >/dev/null 2>&1 || (echo "Initializing git repo..." && git init && git add -A && git commit -m "feat: medical translation + glossary + telegraph + study-pro TOC" && git branch -M main)
	@if [ -z "$$GITHUB_REPO" ]; then echo "Set GITHUB_REPO=https://github.com/USERNAME/REPO.git"; exit 1; fi
	@if [ -z "$$GITHUB_TOKEN" ]; then echo "Set GITHUB_TOKEN=your_token"; exit 1; fi
	@git remote remove origin >/dev/null 2>&1 || true
	@git remote add origin $$(echo $$GITHUB_REPO | sed "s#https://#https://$$GITHUB_TOKEN@#")
	@git add -A && git commit -m "chore: update" || true
	@git push -u origin main

