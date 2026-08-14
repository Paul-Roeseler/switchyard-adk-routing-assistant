.PHONY: setup embed switchyard chat

setup:
	uv sync

embed:
	uv run --env-file .env python scripts/embed_documents.py

switchyard:
	uv run --env-file .env switchyard serve --routing-profiles config/routes.yaml --host 127.0.0.1 --port 4000

chat:
	mkdir -p .adk
	uv run --env-file .env adk web --port 8000 --session_service_uri sqlite:///.adk/sessions.db .
