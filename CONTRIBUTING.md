# Contributing to JARVIS

Thank you for your interest in contributing to JARVIS — a modular AI desktop assistant.
This document explains how to contribute, coding standards, branch workflow, and testing guidelines.

Getting started
- Fork the repository and create a feature branch from `main`.
- Follow the commit message style: `type(scope): short description` (e.g., `feat(voice): add wakeword detector`).

Development workflow
1. Create a virtual environment (Python 3.12):
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
2. Install dependencies:
   pip install -r requirements.txt
3. Run tests:
   pytest -q
4. Format code and run linters (or pre-commit will do it):
   ruff check .
   black --check .
   mypy .

Testing
- Add unit tests for all new functionality under `tests/`.
- Use `pytest-asyncio` for async tests.

Pull Requests
- Open a PR against the `main` branch.
- Ensure all tests pass and linters succeed.
- Provide a clear description and link to any issue it fixes.

Code style
- Follow PEP8 and the project's pyproject.toml formatting rules (Black, Ruff, isort).

Security
- Do not commit secrets. Use .env and .env.example for configuration.

Thank you for contributing!
