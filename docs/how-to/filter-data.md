# Filter Data

The Results SDK accepts Django-style field lookups as keyword arguments.
This guide documents the filter syntax and confirmed live filters.

## Filter Syntax

Filters follow the Django double-underscore convention:

```python
# Exact match
api.list_analyses(name="Windfarm_weld_inspection")

# Nested relation lookup
api.list_analyses(model_definition__id=12)

# Case-insensitive contains
api.list_analyses(name__icontains="weld")

# Greater-than-or-equal timestamp
api.list_analyses(timestamp__gte="2025-01-01T00:00:00Z")
```

## Confirmed Analysis Filters

These filters were validated against the live dev route
`/api/v1/results/routes/analysis/`:

| Filter | Example |
|--------|---------|
| `name` | `name="Windfarm_weld_inspection"` |
| `name__icontains` | `name__icontains="weld"` |
| `source_type` | `source_type="json"` |
| `model_definition__id` | `model_definition__id=12` |
| `model_definition__title` | `model_definition__title="as-built Windfarm"` |
| `project__title` | `project__title="Windfarm"` |
| `timestamp__gte` | `timestamp__gte="2025-01-01T00:00:00Z"` |

## Confirmed Result Filters

These filters were validated against the live dev route
`/api/v1/results/routes/result/`:

| Filter | Example |
|--------|---------|
| `analysis__id` | `analysis__id=46` |
| `analysis__name` | `analysis__name="LifetimeDesignFrequencies"` |
| `location__id` | `location__id=435` |
| `location__title` | `location__title="BBA01"` |
| `short_description` | `short_description="BBA01 - FA1"` |
| `model_definition__id` | `model_definition__id=12` |
| `project__title` | `project__title="Windfarm"` |
| `name_col1` | `name_col1="reference_index"` |
| `name_col2` | `name_col2="FA1"` |
| `timestamp__gte` | `timestamp__gte="2025-01-01T00:00:00Z"` |

## Combining Filters

Multiple keyword arguments are combined with AND logic:

```python
api.list_results(
    analysis__id=46,
    location__id=435,
    name_col2="FA1",
)
```

!!! warning "Django ORM vs. live route"
    The full Django QuerySet surface (e.g. `additional_data__result_scope`,
    direct `id` filtering) is wider than what the public REST route
    exposes. The SDK convenience methods rewrite common shortcuts — for
    example `analysis=46` becomes `analysis__id=46` — but prefer the
    confirmed nested filter names for direct route calls.
