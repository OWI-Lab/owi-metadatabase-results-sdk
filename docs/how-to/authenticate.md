# Authenticate

The Results SDK uses token-based authentication against the OWI Metadatabase
REST API.

## Option 1 — Pass the Token Directly

```python
from owi.metadatabase.results import ResultsAPI

api = ResultsAPI(
    api_root="https://owimetadatabase-dev.azurewebsites.net/api/v1",
    token="your-api-token",
)
```

## Option 2 — Load From a `.env` File

Store the token in a `.env` file at your project root:

```text
OWI_METADATABASE_API_TOKEN="your-api-token"
```

Then load it with the built-in helper:

```python
from pathlib import Path
from owi.metadatabase.results import ResultsAPI
from owi.metadatabase.results.utils import load_token_from_env_file

token = load_token_from_env_file(Path(".env"), "OWI_METADATABASE_API_TOKEN")

api = ResultsAPI(
    api_root="https://owimetadatabase-dev.azurewebsites.net/api/v1",
    token=token,
)
```

## Option 3 — Export as an Environment Variable

```bash
export OWI_METADATABASE_API_TOKEN="your-api-token"
```

Then read it in Python:

```python
import os
from owi.metadatabase.results import ResultsAPI

api = ResultsAPI(
    api_root="https://owimetadatabase-dev.azurewebsites.net/api/v1",
    token=os.environ["OWI_METADATABASE_API_TOKEN"],
)
```

## Verify Connectivity

```python
print(api.ping())
```

A successful response confirms the token and API root are configured
correctly.
