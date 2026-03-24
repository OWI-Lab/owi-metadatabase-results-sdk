# Testing

## Running Tests

```bash
uv run invoke test.run
```

This executes pytest with coverage reporting for `src/owi/metadatabase/results`.

## Test Structure

Tests live under `tests/` and mirror the source layout:

- `tests/` — top-level test configuration and fixtures
- Test files follow the `test_<module>.py` naming convention

## Doctests

Doctests embedded in module docstrings are collected automatically during
test runs. The `pyproject.toml` enables `--doctest-modules` for the `src`
directory.

## Coverage

After running tests, a coverage HTML report is generated. To serve it:

```bash
uv run invoke test.coverage
```

To stop the coverage server:

```bash
uv run invoke test.stop
```
