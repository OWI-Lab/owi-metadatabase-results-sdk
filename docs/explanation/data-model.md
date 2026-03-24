# Data Model

The OWI Metadatabase organises offshore wind data across three Django apps:
**locations**, **geometry**, and **results**. This page explains how those
models relate to each other using the exact schema defined in the backend.

## Full Entity Relationship Diagram

```mermaid
erDiagram
    ProjectSite {
        int id PK
        string title
        string slug
        string description "nullable"
        boolean active
        string visibility
        json additional_data "nullable"
        int created_by FK
        int modified_by FK
    }

    Location {
        int id PK
        int projectsite_id FK
        int created_by FK
        int modified_by FK
    }

    AssetLocation {
        int location_id PK "inherits Location"
        string title
        float northing
        float easting
    }

    ModelDefinition {
        int id PK
        int project_id FK "→ ProjectSite"
        string title
        string description
    }

    SubAssembly {
        int id PK
        int model_definition_id FK
        int asset_location_id FK
    }

    BuildingBlock {
        int id PK
        int sub_assembly_id FK
    }

    TubularSection {
        int building_block_id PK
        int material_id FK
    }

    LumpedMass {
        int building_block_id PK
    }

    DistributedMass {
        int building_block_id PK
    }

    Material {
        int id PK
    }

    Analysis {
        int id PK
        int model_definition_id FK
        int location_id FK "nullable"
        string name
        string source_type
        string source "nullable"
        string description "nullable"
        string user
        datetime timestamp
        json additional_data "nullable"
        string slug
    }

    Result {
        int id PK
        int analysis_id FK
        int site_id FK
        int location_id FK
        string name_col1
        string name_col2
        string name_col3 "nullable"
        string units_col1
        string units_col2
        string units_col3 "nullable"
        float_array value_col1
        float_array value_col2
        float_array value_col3 "nullable"
        string short_description
        string description "nullable"
        json additional_data "nullable"
        string slug
    }

    ProjectSite ||--o{ Location : "projectsite_id"
    Location ||--o| AssetLocation : "location_id"
    ProjectSite ||--o{ ModelDefinition : "project_id"
    ModelDefinition ||--o{ SubAssembly : "model_definition_id"
    AssetLocation ||--o{ SubAssembly : "asset_location_id"
    SubAssembly ||--o{ BuildingBlock : "sub_assembly_id"
    BuildingBlock ||--o| TubularSection : "building_block_id"
    BuildingBlock ||--o| LumpedMass : "building_block_id"
    BuildingBlock ||--o| DistributedMass : "building_block_id"
    Material ||--o{ TubularSection : "material_id"
    ModelDefinition ||--o{ Analysis : "model_definition_id"
    AssetLocation o|--o{ Analysis : "location_id"
    Analysis ||--o{ Result : "analysis_id"
    ProjectSite o|--o{ Result : "site_id"
    AssetLocation o|--o{ Result : "location_id"
```

## Locations Domain

### ProjectSite

The top-level container. Each offshore wind farm is a `ProjectSite` with a
unique `slug`.

**Real example:** `id=31`, `slug="nobelwind"`, `title="Nobelwind"`.

### Location

A generic spatial record linked to a `ProjectSite` via `projectsite_id`.

### AssetLocation

Extends `Location` through **multi-table inheritance** — the
`location_id` column is both the primary key and a one-to-one FK back to
`Location`. Carries asset-specific attributes like `title`, `northing`,
and `easting`.

```mermaid
flowchart TD
    PS[ProjectSite] -->|1:N| L[Location]
    L -->|1:1| AL[AssetLocation]
```

## Geometry Domain

### ModelDefinition

A geometry model version (e.g. "as-built Belwind"). FK `project` points
to `ProjectSite`.

**Real example:** `id=12`, `title="as-built Belwind"`, `project=35`.

### SubAssembly

Links a `ModelDefinition` to an `AssetLocation`, representing a specific
turbine structure instance.

### BuildingBlock

A structural element belonging to a `SubAssembly`. Each building block
may specialise into exactly one of:

- **TubularSection** — cylindrical shell with a `Material` FK.
- **LumpedMass** — point mass.
- **DistributedMass** — distributed mass.

```mermaid
flowchart TD
    MD[ModelDefinition] -->|1:N| SA[SubAssembly]
    AL[AssetLocation] -->|1:N| SA
    SA -->|1:N| BB[BuildingBlock]
    BB -->|1:1| TS[TubularSection]
    BB -->|1:1| LM[LumpedMass]
    BB -->|1:1| DM[DistributedMass]
    TS -->|N:1| MAT[Material]
```

## Results Domain

### Analysis

A named collection of results tied to a `ModelDefinition` and optionally
scoped to a specific `AssetLocation`.

**Real example:** `id=5`, `name="Belwind_weld_inspection"`,
`model_definition=12`, `source_type="json"`.

### Result

Stores typed, multi-column array data. Each row brings:

- Up to **three named columns** (`name_col1`/`name_col2`/`name_col3`)
  with corresponding **units** and **value arrays** (`ArrayField(float)`).
- A `short_description` serving as a stable merge key.
- An `additional_data` `JSONField` for structured metadata
  (e.g. `result_scope`, `analysis_kind`, `reference_labels`).

**Real example:** `id=3372`, `analysis=46`, `site=35`, `location=435`,
`name_col1="reference_index"`, `name_col2="FA1"`,
`value_col1=[0.0, 1.0, 2.0]`, `value_col2=[0.3406, 0.333, 0.3254]`.

### Cross-Domain Relationships

```mermaid
flowchart LR
    PS[ProjectSite]
    MD[ModelDefinition]
    AL[AssetLocation]
    A[Analysis]
    R[Result]

    PS --> MD --> A --> R
    PS --> AL --> A
    PS --> R
    AL --> R
```

Results connect the locations, geometry, and analysis domains.
`Result.site` points to `ProjectSite`, `Result.location` points to
`AssetLocation`, and `Result.analysis` links back through
`Analysis.model_definition` to the geometry tree.
