# Code Style & Conventions

## 1. General Principles
- Readable code over clever code. Small, focused functions. Consistency over novelty.
- Reuse existing utilities. No unnecessary abstractions or dependencies.
- Type hints on all public functions. Docstrings on public functions and modules in the analytics package.

## 2. Naming
Files/modules: snake_case.py
Functions and variables: snake_case
Classes (models, schemas): PascalCase
Constants: UPPER_SNAKE_CASE
Database tables: plural snake_case; columns: snake_case
API routes: lowercase, plural nouns, kebab-case if multi-word (e.g. /uploads, /flagged-transactions)
Rule codes: R1..R6 as constants in one place (`app/analytics/rules.py`)

## 3. Folder Structure
See ARCHITECTURE.md section 7. Layers: routers -> services -> repositories/models; analytics is a separate pure package.

## 4. Imports
- Standard library, third-party, local - separated by blank lines (ruff isort handles this).
- Absolute imports from the `app` package. No wildcard imports.

## 5. Functions
- One logical job per function. Pure functions in analytics (no I/O, no globals, no hidden randomness - pass the seed).
- Avoid functions longer than about 40 lines; split them.

## 6. Pandas Rules
- Vectorized operations only; no `iterrows` on the full dataset.
- Never mutate the input DataFrame; work on a copy.
- Explicit dtypes when reading files. Parse dates with `pd.to_datetime(errors="coerce")` and count failures.

## 7. Error Handling
Use: custom exceptions in the service layer mapped to HTTP errors in routers (FastAPI exception handlers); consistent error JSON shape (see API.md).
Do not: swallow exceptions, use bare `except:`, return raw stack traces to the client.

## 8. Comments
Explain why, tradeoffs, and non-obvious behavior. Do not repeat what the code says.
Every audit rule function must reference its code (R1..R6) in its docstring.

## 9. Logging
Use: Python `logging` (structured, no print statements).
Rules: log run start/end, row counts, durations, errors. Never log passwords, tokens, or raw transaction contents.

## 10. Formatting
Formatter and linter: ruff (line length 100). Type checking: mypy (optional, on app/analytics at least).
Config in pyproject.toml.

## 11. Do
- Follow existing patterns, keep changes focused, remove dead code, write tests with the code.

## 12. Don't
- Create duplicate utilities, hard-code thresholds outside the settings object, put business logic in Streamlit, change unrelated files.
