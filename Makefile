.PHONY: install test demo

install:
	uv sync

test:
	uv run pytest -q

demo:
	uv run babel-bench demo
