test:
    uv run pytest
lint:
    uv run ruff format .
    uv run ruff check --fix .
    uv run vulture
