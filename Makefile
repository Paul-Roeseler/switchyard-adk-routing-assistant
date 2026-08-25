.PHONY: setup switchyard chat test reset-tickets

setup:
	uv sync

switchyard:
	uv run --env-file .env switchyard serve --routing-profiles switchyard.yaml --host 127.0.0.1 --port 4000

chat:
	mkdir -p .adk
	uv run --env-file .env adk web --port 8000 --session_service_uri sqlite:///.adk/sessions.db .

test:
	uv run python -m unittest discover -s tests

reset-tickets:
	rm -f .adk/employee_it.json
