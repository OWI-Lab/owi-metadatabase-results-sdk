# Reference

Reference documentation is **information-oriented**. It provides precise
technical descriptions of every module, class, and function in the SDK,
alongside Django QuerySet examples for the backend schema.

## API Reference

Auto-generated documentation pulled from source code docstrings:

| Module | Description |
|--------|-------------|
| [Results API](api/io.md) | `ResultsAPI` — the primary HTTP client. |
| [Models](api/models.md) | Pydantic data models: `AnalysisDefinition`, `ResultSeries`, `ResultQuery`, etc. |
| [Analyses](api/analyses.md) | Concrete analysis implementations and the `BaseAnalysis` mixin. |
| [Services](api/services.md) | `ResultsService`, `ApiResultsRepository`, and helper functions. |
| [Plotting](api/plotting.md) | Plot strategies, theme helpers, and response builders. |
| [Serializers](api/serializers.md) | `DjangoAnalysisSerializer`, `DjangoResultSerializer`. |
| [Protocols](api/protocols.md) | Runtime-checkable protocols defining the SDK contract. |
| [Utilities](api/utils.md) | Helper functions for logging and token loading. |

## Query Examples

Django QuerySet examples for the backend schema, showing how the SDK
filters map to the underlying ORM:

| Page | Scope |
|------|-------|
| [Analysis Queries](query-examples/analyses.md) | Querying and traversing `Analysis` rows. |
| [Result Queries](query-examples/results.md) | Querying `Result` rows, `ArrayField`, and `JSONField`. |
| [Location & Geometry Queries](query-examples/locations-geometry.md) | Project sites, locations, asset locations, and geometry hierarchy. |
