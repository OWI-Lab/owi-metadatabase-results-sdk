# Upload Results

This guide shows how to create an analysis and persist result rows to the
backend through `ResultsAPI`.

## Create an Analysis

```python
from owi.metadatabase.results import ResultsAPI
from owi.metadatabase.results.models import AnalysisDefinition
from owi.metadatabase.results.serializers import DjangoAnalysisSerializer

api = ResultsAPI(api_root="https://owimetadatabase-dev.azurewebsites.net/api/v1",
                 token="your-api-token")

definition = AnalysisDefinition(
    name="LifetimeDesignFrequencies",
    model_definition_id=12,
    location_id=None,
    source_type="notebook",
    source="scripts/data/results-example-data.xlsx",
    description="Lifetime design frequencies for Belwind.",
    additional_data={"sheet_name": "Lifetime -  Design frequencies"},
)

serializer = DjangoAnalysisSerializer()
payload = serializer.to_payload(definition)
created = api.create_analysis(payload)

analysis_id = int(created["id"])
print(f"Created analysis: {analysis_id}")
```

## Upload Result Rows

Each result payload maps to a single `Result` row in the backend.
`ResultsAPI.create_results_bulk(...)` renders a `tqdm` progress bar automatically.

```python
from owi.metadatabase.results.serializers import DjangoResultSerializer

result_serializer = DjangoResultSerializer()

# Build payload from a ResultSeries object.
# analysis.to_results() returns a list of ResultSeries after validation.
payloads = [
    {**result_serializer.to_payload(series, analysis_id=analysis_id)}
    for series in result_series
]

# Bulk upload all payloads.
response = api.create_results_bulk(payloads)
print(f"Uploaded: {response['exists']}")
```

## Upload a Single Row

If bulk upload is not supported by the target backend, the SDK can also
create results one at a time:

```python
from tqdm.auto import tqdm

for payload in tqdm(payloads, desc="Uploading result rows", unit="row"):
    api.create_result(payload)
```

## Skipping Rows Without Resolved Locations

When working with location-scoped results, filter out rows where the
turbine name could not be mapped to a backend location id:

```python
upload_payloads = [p for p in payloads if p.get("location") is not None]
api.create_results_bulk(upload_payloads)
```

## Create or Update Results in Bulk

When re-uploading data that may partially overlap with existing backend
rows, use `create_or_update_results_bulk`. The method matches rows within
the same analysis by their `short_description` and either creates or
patches each one accordingly.

Every payload **must** include both `analysis` (the analysis id) and
`short_description` keys:

```python
payloads = [
    {"analysis": analysis_id, "short_description": "BBA01 - FA1", "name_col1": "frequency", ...},
    {"analysis": analysis_id, "short_description": "BBA02 - FA1", "name_col1": "frequency", ...},
]

result = api.create_or_update_results_bulk(payloads)
print(result["summary"])  # list of {analysis, short_description, result_id, action}
```

The returned `summary` list indicates the `action` taken for each row:

| Action | Meaning |
|--------|---------|
| `created` | No matching row existed; a new row was inserted. |
| `updated` | An existing row with the same `short_description` was patched. |

!!! warning "Ambiguous matches"
    If the backend already contains **multiple** rows with the same
    `short_description` for a given analysis, the call raises
    `InvalidParameterError` to avoid silent data corruption.
    Resolve the duplicates on the backend first, then retry.
