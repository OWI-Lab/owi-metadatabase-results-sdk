# Scripts And Notebooks

This folder contains terminal scripts and matching Jupyter notebooks for the results SDK workflows.

## Files

- `notebook_results_demo.py`
  Terminal reimplementation of the legacy results upload notebook.
- `notebook_results_demo.ipynb`
  Notebook version of the same flow.
- `upload_results_example_data.py`
  Reads `data/results-example-data.xlsx` and prepares or uploads the workbook analyses.
- `upload_results_example_data.ipynb`
  Notebook version of the workbook workflow.
- `plot_analyses_and_results.ipynb`
  Demonstrates retrieval and plotting of results with `pyecharts`.

## Environment

Authenticated examples use the `OWI_METADATABASE_API_TOKEN` environment variable.

Typical shell setup:

```bash
source ~/.zshrc
export OWI_METADATABASE_API_TOKEN="$OWI_METADATABASE_API_TOKEN"
```

If your shell does not propagate the token into `uv run`, use:

```bash
env OWI_METADATABASE_API_TOKEN="$OWI_METADATABASE_API_TOKEN" uv run python scripts/notebook_results_demo.py --upload
```

## Running The Scripts

Dry-run notebook demo:

```bash
uv run python scripts/notebook_results_demo.py
```

Live notebook demo:

```bash
env OWI_METADATABASE_API_TOKEN="$OWI_METADATABASE_API_TOKEN" uv run python scripts/notebook_results_demo.py --upload
```

Dry-run workbook upload:

```bash
uv run python scripts/upload_results_example_data.py
```

Live workbook upload:

```bash
env OWI_METADATABASE_API_TOKEN="$OWI_METADATABASE_API_TOKEN" uv run python scripts/upload_results_example_data.py --upload
```

## Working With The Notebooks

Open any `.ipynb` file in VS Code and select the project kernel.

Suggested order:

1. `notebook_results_demo.ipynb`
2. `upload_results_example_data.ipynb`
3. `plot_analyses_and_results.ipynb`

The notebooks are structured so they can run in dry-run mode when the token is missing.

## Current Backend Caveats

- The dev backend supports the notebook demo upload flow.
- The workbook workflow skips rows that cannot be resolved to backend `location` ids.
- When the backend does not allow the bulk results endpoint, the client falls back to single-result POST requests.
- Some workbook values may need cleaning before upload if the source sheet contains non-finite numeric values.
