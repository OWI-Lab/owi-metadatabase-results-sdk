# Copilot instructions for owi-metadatabase-sdk

## Big picture
- Core package lives in src/owi/metadatabase and is a namespace package; __init__.py extends the namespace with pkgutil.extend_path for future extensions.
- Data access flows through the base API class in src/owi/metadatabase/io.py: build auth headers, send requests, check status, decode JSON to DataFrame, validate/postprocess, and return (df, info).
- Geometry is in src/owi/metadatabase/geometry (GeometryAPI + OWT/OWTs processing); Locations is in src/owi/metadatabase/locations (LocationsAPI). GeometryAPI internally uses LocationsAPI for lookups.

## Conventions and patterns
- API methods typically return a dict with keys like "data" (pandas DataFrame) and "exists" (bool), sometimes "id"; follow this pattern when adding new endpoints.
- Base API errors use custom exceptions in src/owi/metadatabase/_utils/exceptions.py; prefer these over generic exceptions for request/processing failures.
- Geometry processing expects calling OWT.process_structure() or OWTs.process_structures() before accessing derived attributes; warnings are emitted if accessed early.
- Code style uses ruff with 120-char lines (see pyproject.toml); keep NumPy-style docstrings and doctests consistent with existing modules.
- Type hints are expected for public methods in src/owi/metadatabase (ty overrides enforce typed defs).
- Prefer f-strings for formatting; if logging is introduced, use the logging module and %-formatting.
- Prefer pandas/numpy for data manipulation to match existing APIs; avoid ad-hoc dict lists when a DataFrame is expected.

## Workflows
- Dev install (recommended): uv sync --dev (see README.md).
- Tests and coverage: uv run invoke test.all (tasks in tasks/test.py). This runs pytest with doctests enabled (see pyproject.toml).
- Lint/format/type checks: uv run invoke quality.all (ruff format/check + ty) in tasks/quality.py.
- Docs: uv run invoke docs.build or docs.serve (tasks/docs.py, zensical).
- Use uv-managed environment; prefer uv run ... for test/quality/docs commands.

## Useful entry points
- Base API and data flow: src/owi/metadatabase/io.py
- Geometry API and plotting: src/owi/metadatabase/geometry/io.py
- Geometry processing models: src/owi/metadatabase/geometry/processing.py
- Geometry data structures: src/owi/metadatabase/geometry/structures.py
- Locations API: src/owi/metadatabase/locations/io.py
- Test runner/quality tasks/docs tasks: tasks/test.py, tasks/quality.py, tasks/docs.py
