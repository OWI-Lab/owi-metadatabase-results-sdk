# OWI-metadatabase Results Extension

Results extension for OWI Metadatabase SDK

[![version](https://img.shields.io/pypi/v/owi-metadatabase-results)](https://pypi.org/project/owi-metadatabase-results/)
[![python versions](https://img.shields.io/pypi/pyversions/owi-metadatabase-results)](https://pypi.org/project/owi-metadatabase-results/)
[![license](https://img.shields.io/github/license/owi-lab/owi-metadatabase-results-sdk)](https://github.com/OWI-Lab/owi-metadatabase-results-sdk/blob/main/LICENSE)
[![pytest](https://img.shields.io/github/actions/workflow/status/owi-lab/owi-metadatabase-results-sdk/ci.yml?label=pytest)](https://github.com/OWI-Lab/owi-metadatabase-results-sdk/actions/workflows/ci.yml)
[![lint](https://img.shields.io/github/actions/workflow/status/owi-lab/owi-metadatabase-results-sdk/ci.yml?label=lint)](https://github.com/OWI-Lab/owi-metadatabase-results-sdk/actions/workflows/ci.yml)
[![issues](https://img.shields.io/github/issues/owi-lab/owi-metadatabase-results-sdk)](https://github.com/OWI-Lab/owi-metadatabase-results-sdk/issues)
[![Documentation](https://img.shields.io/badge/docs-zensical-blue)](https://owi-lab.github.io/owi-metadatabase-results-sdk/)

## Overview

This package extends [`owi-metadatabase`](https://pypi.org/project/owi-metadatabase/) SDK under the `owi.metadatabase.*` namespace so it behaves like the existing extension packages.

📚 **[Read the Documentation](https://owi-lab.github.io/owi-metadatabase-results-sdk/)**

## Installation

### Install as extension package (`owi-metadatabase-results`)

```bash
pip install owi-metadatabase-results
```

Using `uv`:

```bash
uv pip install owi-metadatabase-results
```

### Install from core package extra (`owi-metadatabase[results]`)

If you prefer installing from the base package extras:

```bash
pip install "owi-metadatabase[results]"
```

Using `uv`:

```bash
uv pip install "owi-metadatabase[results]"
```

## Quick Start

```python
from owi.metadatabase.results import ResultsAPI

api = ResultsAPI(token="your-api-token")
print(api.ping())
```

## Architecture At A Glance

The diagram below shows how the package is structured, which parts are core, and how data moves from domain payloads to backend persistence and plots.

```mermaid
flowchart TD
  User[User Code / Notebooks / Scripts] --> Service[services.py\nResultsService\nHigh-level facade]
  User --> API[io.py\nResultsAPI\nLow-level HTTP client]

  Service --> Repo[services.py\nApiResultsRepository]
  Repo --> API

  Service --> Registry[registry.py\nAnalysis registry]
  Registry --> BaseAnalysis[analyses/base.py\nShared analysis contract]

  BaseAnalysis --> Freq[analyses/lifetime_design_frequencies.py\nComparison + location + geo frequencies]
  BaseAnalysis --> Verify[analyses/lifetime_design_verification.py\nTime-series verification]
  BaseAnalysis --> Hist[analyses/wind_speed_histogram.py\nHistogram analysis]
  BaseAnalysis --> CEIT[ceit.py\nCEIT import + merge + plot helpers]

  Freq --> Models[models.py\nAnalysisDefinition\nResultSeries\nResultVector\nResultQuery\nPlotRequest/Response]
  Verify --> Models
  Hist --> Models
  CEIT --> Models

  Models --> Serializers[serializers.py\nDjango payload mapping]
  Serializers --> API

  Service --> Plotting[plotting.py\nGeneric histogram/time-series rendering]
  Freq --> FrequencyPlots[frequency_plots.py\nSpecialized comparison/location/geo plots]
  Plotting --> PlotResponse[PlotResponse\nHTML + notebook widget + chart options]
  FrequencyPlots --> PlotResponse

  Service -. location metadata for geo plots .-> Locations[owi.metadatabase.locations.io\nLocationsAPI]
  Locations -. coordinates and titles .-> FrequencyPlots
  Locations -. asset/site identifiers .-> Repo

  Geometry[owi.metadatabase.geometry\nOWT / subassembly context] -. joined by site/location identifiers .-> User

  classDef core fill:#d9f2e6,stroke:#2c7a4b,color:#143d28;
  classDef domain fill:#e8eefc,stroke:#3559b7,color:#1e2f63;
  classDef infra fill:#f7ead9,stroke:#b7791f,color:#5a3d0c;
  classDef external fill:#f3f4f6,stroke:#6b7280,color:#374151;

  class Service,Repo,Registry,BaseAnalysis,Plotting,FrequencyPlots core;
  class Freq,Verify,Hist,CEIT,Models,PlotResponse,Serializers domain;
  class API infra;
  class User,Locations,Geometry external;
```

## Data Model At A Glance

The results extension stores analysis metadata separately from persisted result rows. Result rows link back to site and location metadata, while geometry stays adjacent and is usually joined through location-aware identifiers.

```mermaid
erDiagram
  ANALYSIS {
    int id PK
    string name
    string source_type
    string source
    string description
    json additional_data
  }

  RESULT {
    int id PK
    int analysis_id FK
    int site FK
    int location FK
    string short_description
    string description
    json additional_data
    json related_object
    string name_col1
    string units_col1
    float_array value_col1
    string name_col2
    string units_col2
    float_array value_col2
    string name_col3
    string units_col3
    float_array value_col3
  }

  PROJECTSITE {
    int id PK
    string title
  }

  ASSETLOCATION {
    int id PK
    int projectsite_id FK
    string title
    float northing
    float easting
  }

  OWT {
    int id PK
    int assetlocation_id FK
    string title
  }

  SUBASSEMBLY {
    int id PK
    int owt_id FK
    string type
  }

  ANALYSIS ||--o{ RESULT : owns
  PROJECTSITE ||--o{ ASSETLOCATION : contains
  PROJECTSITE ||--o{ RESULT : site_scope
  ASSETLOCATION ||--o{ RESULT : location_scope
  ASSETLOCATION ||--|| OWT : anchors
  OWT ||--o{ SUBASSEMBLY : contains
```

Interpretation:

- `ANALYSIS` stores one logical analysis definition, such as `LifetimeDesignVerification` or `WindSpeedHistogram`.
- `RESULT` stores one persisted series row with 2 to 3 aligned numeric vectors plus JSON metadata.
- `PROJECTSITE` and `ASSETLOCATION` come from the locations package and provide the site and asset identifiers used by result queries.
- `northing` and `easting` on `ASSETLOCATION` are what make geo-oriented result plots possible.
- Geometry objects like `OWT` and `SUBASSEMBLY` are not owned by the results package, but they are the physical context users typically join onto result rows through location/site relationships.

## Development

```bash
uv sync --dev
uv run invoke test
uv run invoke qa
uv run invoke docs.build
```
