# Your First Results Query

!!! example
    This tutorial walks you through connecting to the OWI Metadatabase,
    listing analyses, and retrieving result rows. By the end you will have
    queried real backend data and inspected a result series in a DataFrame.

## Prerequisites

- Python 3.10+
- The SDK installed (`pip install owi-metadatabase-results`)
- A valid API token (see [How to Authenticate](../how-to/authenticate.md))

## Step 1 — Create a ResultsAPI Client

```python
from owi.metadatabase.results import ResultsAPI

api = ResultsAPI(
    api_root="https://owimetadatabase-dev.azurewebsites.net/api/v1",
    token="your-api-token",
)

# Verify connectivity
print(api.ping())
```

## Step 2 — List Analyses

```python
# Retrieve every analysis the backend knows about.
analyses = api.list_analyses()
print(analyses["data"].head())
```

The returned dict contains:

| Key | Type | Description |
|-----|------|-------------|
| `data` | `DataFrame` | Tabular representation of analysis rows. |
| `exists` | `bool` | `True` when at least one row was returned. |

## Step 3 — Filter to a Specific Analysis

```python
# Filter by name
analysis = api.get_analysis(name="Windfarm_weld_inspection")
print(analysis)
```

You can also filter using nested relation lookups — exactly the same
field names accepted by the Django REST backend:

```python
api.list_analyses(model_definition__id=12)
api.list_analyses(project__title="Windfarm")
```

## Step 4 — Retrieve Results for an Analysis

```python
# List all result rows attached to analysis id 46.
results = api.list_results(analysis__id=46)
print(results["data"].head())
```

Each result row stores up to three column vectors (`value_col1`,
`value_col2`, `value_col3`) alongside their semantic names and units.

## Step 5 — Inspect a Single Result Row

```python
# Fetch one raw result row by passing backend filters.
raw = api.get_results_raw(id=3372)

# Look at the array data stored in the row.
print("Column 1:", raw["name_col1"], raw["units_col1"])
print("Column 2:", raw["name_col2"], raw["units_col2"])
print("Values:", list(zip(raw["value_col1"], raw["value_col2"])))
```

## Step 6 — Use ResultsService for Higher-level Access

The `ResultsService` facade provides typed deserialization and
integrated plotting on top of the raw API:

```python
from owi.metadatabase.results import ResultsService, ResultsAPI
from owi.metadatabase.results.services import ApiResultsRepository

api = ResultsAPI(api_root="https://owimetadatabase-dev.azurewebsites.net/api/v1",
                 token="your-api-token")
service = ResultsService(repository=ApiResultsRepository(api=api))

# Retrieve typed result series and reconstruct the normalized frame.
frame = service.get_results("LifetimeDesignFrequencies",
                            filters={"analysis_id": 46})
print(frame.head())
```

## What You Learned

- How to create and configure a `ResultsAPI` client.
- How to list and filter analyses using backend field lookups.
- How to retrieve result rows and inspect array-valued columns.
- How to use `ResultsService` for higher-level typed access.

## Next Steps

- [Lifetime Design Frequencies Workflow](lifetime-design-frequencies.md) —
  a full end-to-end tutorial from workbook upload to interactive plots.
- [How-to: Upload Results](../how-to/upload-results.md) — a focused recipe
  for persisting data to the backend.
