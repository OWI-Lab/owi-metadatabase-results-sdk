# Plot Results

This guide shows how to render interactive charts from persisted results.

## Prerequisites

- Results already uploaded to the backend (see [Upload Results](upload-results.md)).
- A `ResultsAPI` client configured and authenticated.

## Plot Through ResultsService

```python
from owi.metadatabase.results import ResultsAPI, ResultsService
from owi.metadatabase.results.services import ApiResultsRepository

api = ResultsAPI(api_root="https://owimetadatabase-dev.azurewebsites.net/api/v1",
                 token="your-api-token")
service = ResultsService(repository=ApiResultsRepository(api=api))
```

## Available Plot Types

### Comparison Plot

Scatter chart comparing metrics across references with a location dropdown:

```python
plot = service.plot_results(
    "LifetimeDesignFrequencies",
    filters={"analysis_id": 46},
    plot_type="comparison",
)
display(plot.notebook)  # Jupyter widget
```

### Location Plot

Scatter chart grouping values by turbine with a metric dropdown:

```python
plot = service.plot_results(
    "LifetimeDesignFrequencies",
    filters={"analysis_id": 46},
    plot_type="location",
)
display(plot.notebook)
```

### Geo Plot

Geographic map projecting results onto the site layout:

```python
plot = service.plot_results(
    "LifetimeDesignFrequencies",
    filters={"analysis_id": 46},
    plot_type="geo",
)
display(plot.notebook)
```

### Time Series Plot

Line chart for time-indexed data (e.g. `LifetimeDesignVerification`):

```python
plot = service.plot_results(
    "LifetimeDesignVerification",
    filters={"analysis_id": 50},
    plot_type="time_series",
)
display(plot.notebook)
```

### Histogram Plot

Bar chart for binned data (e.g. `WindSpeedHistogram`):

```python
plot = service.plot_results(
    "WindSpeedHistogram",
    filters={"analysis_id": 55},
    plot_type="histogram",
)
display(plot.notebook)
```

## Access Plot Outputs

Every `PlotResponse` provides multiple output formats:

| Attribute | Type | Description |
|-----------|------|-------------|
| `notebook` | widget/`None` | Jupyter-compatible widget for inline display. |
| `html` | `str`/`None` | Standalone HTML string for embedding. |
| `json_options` | `dict`/`None` | Raw chart configuration for custom rendering. |
| `chart` | object/`None` | The underlying pyecharts chart object. |
