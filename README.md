# OWI-metadatabase Results Extension

Results extension for OWI Metadatabase SDK

[![version](https://img.shields.io/pypi/v/owi-metadatabase-results)](https://pypi.org/project/owi-metadatabase-results/)
[![python versions](https://img.shields.io/pypi/pyversions/owi-metadatabase-results)](https://pypi.org/project/owi-metadatabase-results/)
[![license](https://img.shields.io/github/license/owi-lab/owi-metadatabase-results-sdk)](https://github.com/OWI-Lab/owi-metadatabase-results-sdk/blob/main/LICENSE)
[![pytest](https://img.shields.io/github/actions/workflow/status/owi-lab/owi-metadatabase-results-sdk/ci.yml?label=pytest)](https://github.com/OWI-Lab/owi-metadatabase-results-sdk/actions/workflows/ci.yml)
[![lint](https://img.shields.io/github/actions/workflow/status/owi-lab/owi-metadatabase-results-sdk/ci.yml?label=lint)](https://github.com/OWI-Lab/owi-metadatabase-results-sdk/actions/workflows/ci.yml)
[![issues](https://img.shields.io/github/issues/owi-lab/owi-metadatabase-results-sdk)](https://github.com/OWI-Lab/owi-metadatabase-results-sdk/issues)
[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](https://owi-lab.github.io/owi-metadatabase-results-sdk/)

**Results extension for OWI Metadatabase SDK**

This package extends `owi-metadatabase` under the `owi.metadatabase.*`
namespace so it behaves like the existing extension packages.

## Installation

### Install as extension package (`owi-metadatabase-results`)

```bash
pip install owi-metadatabase-results
```

Using `uv`:

```bash
uv pip install owi-metadatabase-results
```

### Install from core package extra (`owi-metadatabase[results]`)

If you prefer installing from the base package extras:

```bash
pip install "owi-metadatabase[results]"
```

Using `uv`:

```bash
uv pip install "owi-metadatabase[results]"
```

## Quick Start

```python
from owi.metadatabase.results import ResultsAPI

api = ResultsAPI(token="your-api-token")
print(api.ping())
```

## Terminal Scripts

The package now ships with two terminal-oriented scripts under [scripts](scripts):

1. [scripts/notebook_results_demo.py](scripts/notebook_results_demo.py)
	Reimplements the legacy upload notebook as a terminal workflow using `rich`.
2. [scripts/upload_results_example_data.py](scripts/upload_results_example_data.py)
	Reads the workbook in [scripts/data/results-example-data.xlsx](scripts/data/results-example-data.xlsx) and prepares or uploads the three example result sheets.

Both scripts use the `OWI_METADATABASE_API_TOKEN` environment variable for authenticated uploads.

Dry-run execution:

```bash
uv run python scripts/notebook_results_demo.py
uv run python scripts/upload_results_example_data.py
```

Authenticated execution:

```bash
source ~/.zshrc
env OWI_METADATABASE_API_TOKEN="$OWI_METADATABASE_API_TOKEN" uv run python scripts/notebook_results_demo.py --upload
env OWI_METADATABASE_API_TOKEN="$OWI_METADATABASE_API_TOKEN" uv run python scripts/upload_results_example_data.py --upload
```

The explicit `env ...` prefix is useful in shells where `uv run` does not automatically inherit the token.
When the backend does not expose the bulk results endpoint, the workbook uploader automatically falls back to single-result POST requests.
Rows that cannot be mapped to a backend `location` are reported and skipped during live workbook uploads because the current dev backend requires `location` on result creation.

## Development

```bash
uv sync --dev
uv run invoke test.run
uv run invoke qa.all
uv run invoke docs.build
```
