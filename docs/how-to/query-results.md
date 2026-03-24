# Query Results

This guide shows how to retrieve analyses and result rows from the backend.

## List All Analyses

```python
from owi.metadatabase.results import ResultsAPI

api = ResultsAPI(api_root="https://owimetadatabase-dev.azurewebsites.net/api/v1",
                 token="your-api-token")

analyses = api.list_analyses()
print(analyses["data"].head())
```

## Filter Analyses

Pass Django-style filter arguments as keyword arguments:

```python
# By name
api.list_analyses(name="Belwind_weld_inspection")

# By model definition
api.list_analyses(model_definition__id=12)

# By project
api.list_analyses(project__title="Belwind")
```

## Get a Single Analysis

```python
analysis = api.get_analysis(name="Belwind_weld_inspection")
print(analysis["data"])
```

## List Results for an Analysis

```python
results = api.list_results(analysis__id=46)
print(results["data"].head())
```

## Filter Results

```python
# By location
api.list_results(location__id=435)

# By short description
api.list_results(short_description="BBA01 - FA1")

# By column name
api.list_results(name_col2="FA1")

# Combined filters
api.list_results(
    analysis__id=46,
    location__id=435,
    short_description="BBA01 - FA1",
)
```

## Get a Raw Result Row

```python
raw = api.get_results_raw(id=3372)
print(raw)
```

## Use ResultsService for Typed Access

The service layer deserializes raw backend rows into typed `ResultSeries`
objects:

```python
from owi.metadatabase.results import ResultsService
from owi.metadatabase.results.services import ApiResultsRepository

service = ResultsService(repository=ApiResultsRepository(api=api))

frame = service.get_results(
    "LifetimeDesignFrequencies",
    filters={"analysis_id": 46},
)
print(frame.head())
```

!!! note "Live route filters"
    The backend route exposes a subset of Django QuerySet filters.
    Confirmed working filters include: `analysis__id`, `analysis__name`,
    `location__id`, `location__title`, `short_description`,
    `model_definition__id`, `project__title`, `name_col1`, `name_col2`.
