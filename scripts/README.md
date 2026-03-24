# Scripts And Notebooks

This folder contains terminal scripts and Jupyter notebooks for the results SDK workflows.

## Files

- `1.0.lifetime-design-frequencies.ipynb`
  Explicit workbook import, POST upload, GET retrieval, and plotting flow for lifetime design frequencies.
- `2.0.lifetime-design-verification.ipynb`
  Explicit workbook-based verification workflow with optional upload and retrieval.
- `3.0.wind-speed-histogram.ipynb`
  Explicit workbook-based histogram workflow with optional upload and retrieval.

## Environment

Authenticated examples use the `OWI_METADATABASE_API_TOKEN` environment variable.

Typical shell setup:

```bash
source ~/.zshrc
export OWI_METADATABASE_API_TOKEN="$OWI_METADATABASE_API_TOKEN"
```

If your shell does not propagate the token into `uv run`, prefix the command with `env OWI_METADATABASE_API_TOKEN="$OWI_METADATABASE_API_TOKEN"`.

## Working With The Notebooks

Open any `.ipynb` file in VS Code and select the project kernel.

Suggested order:

1. `1.0.lifetime-design-frequencies.ipynb`
2. `2.0.lifetime-design-verification.ipynb`
3. `3.0.wind-speed-histogram.ipynb`

The notebooks are structured so they can run in dry-run mode when the token is missing.

## Current Backend Caveats

- The dev backend supports the explicit notebook upload flows.
- The workbook workflow skips rows that cannot be resolved to backend `location` ids.
- When the backend does not allow the bulk results endpoint, the client falls back to single-result POST requests.
- Some workbook values may need cleaning before upload if the source sheet contains non-finite numeric values.
