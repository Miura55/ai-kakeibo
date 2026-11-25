# Repository Guidelines

## Project Structure & Module Organization

This is a Python 3.13+ Streamlit application. `main.py` contains the UI and receipt OCR flow; `database.py` defines the SQLAlchemy transaction model and database operations. `.streamlit/config.toml` contains the app theme, while `pyproject.toml` and `uv.lock` define dependencies. `data/kakeibo.db` is created locally and ignored by Git. `sample.JPG` is a sample image asset. There is no `tests/` directory yet.

## Build, Test, and Development Commands

- `uv sync` installs the locked project dependencies.
- `ollama pull glm-ocr:latest` downloads the local OCR model.
- `uv run streamlit run main.py` starts the app.
- `uv run python -m py_compile main.py database.py` checks Python syntax.
- `uv run python -m unittest discover -s tests` runs standard-library tests if a `tests/` directory is added.

Update `pyproject.toml` and regenerate `uv.lock` with `uv lock` whenever dependencies change.

## Coding Style & Naming Conventions

Use four spaces for indentation and standard Python naming: `snake_case` for functions and variables, `PascalCase` for ORM classes, and uppercase names for constants. Add type hints to database helpers and keep persistence logic in `database.py`; keep Streamlit rendering and interaction in `main.py`. Use parameterized ORM operations and commit each database change through a session.

## Testing Guidelines

No test framework or coverage requirement is configured. Add tests under `tests/` as `test_*.py`, especially for amount normalization and ORM CRUD behavior. Keep database tests isolated with a temporary SQLite file so they never alter `data/kakeibo.db`.

## Commit & Pull Request Guidelines

The repository has no commits yet, so no established commit convention can be inferred. Use short imperative subjects such as `Add income categories`. Pull requests should summarize user-visible changes, list validation commands and results, and include screenshots for UI changes.

## Security & Local Data

Keep API keys and credentials out of source control. Ollama defaults to `localhost:11434`; verify the configured host before sending receipt images. Do not commit `.env`, `.streamlit/secrets.toml`, or files under `data/` because they may contain private configuration or financial records.
