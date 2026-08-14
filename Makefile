.PHONY: setup embed switchyard chat test

setup:
	uv sync

embed:
	uv run --env-file .env python scripts/embed_documents.py

switchyard:
	uv run --env-file .env python scripts/switchyard_server.py

chat:
	mkdir -p .adk
	uv run --env-file .env adk web --port 8000 --session_service_uri sqlite:///.adk/sessions.db .

test:
	uv run python -m unittest discover -s tests
