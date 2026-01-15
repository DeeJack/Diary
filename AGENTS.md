# Repository Guidelines

## Project Structure & Module Organization
- `src/diary/` contains the application code (models, UI, utils, config).
- `src/diary/models/` holds the data model and DAO layer; `src/diary/ui/` contains PyQt6 UI, widgets, and graphics items.
- `tests/` contains pytest suites (e.g., `tests/test_backup_manager.py`).
- `assets/` stores static assets (see `assets/example.png`).
- Tooling and scripts live at the repo root (`build.py`, `create_large_notebook.py`).

## Build, Test, and Development Commands
- `pip install .` installs the package into the active venv.
- `poetry install` installs dependencies with Poetry.
- `python -m diary.main` runs the app locally.
- `poetry run build-executable` builds a PyInstaller one-file executable (`build.py`).
- `pytest` runs the test suite.
- `basedpyright` and `mypy` run type checks; `pylint src/diary` runs linting.

## Coding Style & Naming Conventions
- Python code uses 4-space indentation and PEP 8 conventions.
- Keep modules and functions in `snake_case`; classes in `PascalCase`.
- Prefer explicit type hints where practical; respect existing pyright/mypy settings in `pyproject.toml`.
- Keep UI-related code under `src/diary/ui/` and model/DAO code under `src/diary/models/`.

## Testing Guidelines
- Framework: pytest.
- Naming: test files use `test_*.py`; test classes use `Test*`; test functions start with `test_`.
- Run all tests with `pytest`; add targeted tests alongside related modules.

## Commit & Pull Request Guidelines
- Commit messages follow a short `type: description` format (e.g., `fix: segfault`, `feat: calendar view`).
- PRs should describe the change, list key files touched, and mention related issues.
- Include screenshots or short clips for UI changes when possible.

## Configuration & Security Notes
- App configuration lives in `src/diary/config.py`; update defaults there.
- Encryption and backup logic are in `src/diary/utils/`—be cautious with file format or key changes.
