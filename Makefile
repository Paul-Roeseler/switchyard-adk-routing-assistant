SWITCHYARD_SERVER := .adk/bin/switchyard-server
SWITCHYARD_VERSION := 0.2.0

.PHONY: setup switchyard chat test reset-tickets check-switchyard-version

setup: check-switchyard-version
	uv sync

$(SWITCHYARD_SERVER):
	cargo install --locked --version $(SWITCHYARD_VERSION) --root .adk switchyard-server

check-switchyard-version: $(SWITCHYARD_SERVER)
	test "$$($(SWITCHYARD_SERVER) --version)" = "switchyard-server $(SWITCHYARD_VERSION)"

switchyard: check-switchyard-version
	uv run --no-sync --env-file .env $(SWITCHYARD_SERVER) --config switchyard.toml --host 127.0.0.1 --port 4000

chat:
	mkdir -p .adk
	uv run --env-file .env adk web --port 8000 --session_service_uri sqlite:///.adk/sessions.db .

test: check-switchyard-version
	INFERENCE_HUB_API=test NEBIUS_API_KEY=test VERTEX_ACCESS_TOKEN=test $(SWITCHYARD_SERVER) --config switchyard.toml --dry-run
	uv run --no-sync python -m unittest discover -s tests

reset-tickets:
	rm -f .adk/employee_it.json
