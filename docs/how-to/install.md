# Install the SDK

## Install as a Standalone Extension

=== "pip"

    ```bash
    pip install owi-metadatabase-results
    ```

=== "uv"

    ```bash
    uv pip install owi-metadatabase-results
    ```

## Install from the Core Package Extra

If the core `owi-metadatabase` package is already in your project, install
the results extra:

=== "pip"

    ```bash
    pip install "owi-metadatabase[results]"
    ```

=== "uv"

    ```bash
    uv pip install "owi-metadatabase[results]"
    ```

## Development Setup

Clone the repository and sync with dev dependencies:

```bash
git clone https://github.com/OWI-Lab/owi-metadatabase-results-sdk.git
cd owi-metadatabase-results-sdk
uv sync --dev
```
