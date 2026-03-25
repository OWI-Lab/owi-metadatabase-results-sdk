# Contributing

## Development Setup

```bash
git clone https://github.com/OWI-Lab/owi-metadatabase-results-sdk.git
cd owi-metadatabase-results-sdk
uv sync --dev
```

## Run Tests

```bash
uv run invoke test.run
```

Or the full pipeline (tests + coverage server):

```bash
uv run invoke test.all
```

## Quality Gate

```bash
uv run invoke qa
```

This runs `ruff format`, `ruff check`, and `ty check`.

## Build Documentation

```bash
uv run invoke docs.build
```

To serve locally with hot reload:

```bash
uv run invoke docs.serve
```

## Pull Request Conventions

- Add exactly one release label: `release:major`, `release:minor`, or
  `release:patch`.
- Keep commits focused and well-described.
- All CI checks must pass before merge.
