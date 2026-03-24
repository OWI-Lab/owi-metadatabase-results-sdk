# OWI Metadatabase Results Extension
!!! abstract "What is the OWI Metadatabase Results SDK?"
    The `owi-metadatabase-results` package extends the `owi.metadatabase` namespace with a full **results lifecycle**: define analyses, persist typed result series, retrieve them with Django-style filters, and render interactive plots. All through a single, [protocol-driven](explanation/architecture.md#protocols) SDK.

<div class="grid cards" markdown>

-   :material-school:{ .lg .middle } **Tutorials**

    ---

    Step-by-step lessons that walk you through complete workflows from
    first API call to rendered plot.

    [:octicons-arrow-right-24: Start learning](tutorials/index.md)

-   :material-tools:{ .lg .middle } **How-to Guides**

    ---

    Focused recipes for common tasks: install, authenticate, upload
    results, plot data, and more.

    [:octicons-arrow-right-24: Find a recipe](how-to/index.md)

-   :material-book-open-variant:{ .lg .middle } **Reference**

    ---

    Auto-generated API docs and Django QuerySet examples for every
    model in the results schema.

    [:octicons-arrow-right-24: Browse reference](reference/index.md)

-   :material-lightbulb-on:{ .lg .middle } **Explanation**

    ---

    Deeper discussions on architecture, data models, and design
    decisions behind the SDK.

    [:octicons-arrow-right-24: Understand concepts](explanation/index.md)

</div>

## Quick Example

```python
from owi.metadatabase.results import ResultsAPI

api = ResultsAPI(token="your-api-token")

# List all analyses
analyses = api.list_analyses()

# Retrieve results for a specific analysis
results = api.list_results(analysis__id=46)
```
