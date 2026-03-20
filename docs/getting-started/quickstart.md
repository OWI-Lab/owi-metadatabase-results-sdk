# Quick Start

```python
from owi.metadatabase.results import ResultsAPI

api = ResultsAPI(token="your-api-token")
print(api.ping())
```

## Run The Terminal Notebook Replacement

Dry-run:

```bash
uv run python scripts/notebook_results_demo.py
```

Authenticated upload to the dev server:

```bash
source ~/.zshrc
env OWI_METADATABASE_API_TOKEN="$OWI_METADATABASE_API_TOKEN" uv run python scripts/notebook_results_demo.py --upload
```

## Upload The Example Workbook

Dry-run workbook parsing:

```bash
uv run python scripts/upload_results_example_data.py
```

Authenticated upload of the example sheets:

```bash
source ~/.zshrc
env OWI_METADATABASE_API_TOKEN="$OWI_METADATABASE_API_TOKEN" uv run python scripts/upload_results_example_data.py --upload
```

If the target backend does not support bulk result creation, the uploader automatically retries with single-result POST requests.
Rows that cannot be resolved to backend locations are reported and skipped in live mode.

The workbook script reads these sheets from [scripts/data/results-example-data.xlsx](../../scripts/data/results-example-data.xlsx):

- `Lifetime - Wind Histogram`
- `Lifetime -  Design verification`
- `Lifetime -  Design frequencies`
