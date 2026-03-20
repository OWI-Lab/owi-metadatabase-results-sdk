# Results Extension

The `owi-metadatabase-results` package extends the
`owi.metadatabase` namespace with results-specific API behavior.

## Scope

- Package and expose extension-specific API helpers
- Keep the namespace package layout consistent with existing extensions
- Provide NumPy-style docstrings and doctest-friendly examples

## Quick Example

```python
from owi.metadatabase.results import ResultsAPI

api = ResultsAPI()
print(api.ping())
```

## Documentation Style

API docstrings in this extension should follow the NumPy docstring convention
and include doctest-style usage examples.
