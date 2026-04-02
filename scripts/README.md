# Scripts And Notebooks

This folder contains Jupyter notebooks that demonstrate the full results SDK workflows:
resolve metadata, load source data, upload results, retrieve persisted rows, and plot.

## Notebooks

### 1.0 — Lifetime Design Frequencies

**`1.0.lifetime-design-frequencies.ipynb`**

Loads an Excel workbook (`results-example-data.xlsx`), detects frequency columns ending
with `[Hz]`, builds one prepared row per turbine and reference with site and location
metadata attached, uploads them under a shared analysis, retrieves the persisted rows,
and plots comparison, location, and geo views.

| Sections | Resolve Metadata · Load Workbook · Build & Upload · Retrieve · Plot |
|---|---|
| Source data | `data/results-example-data.xlsx` |
| SDK packages | `owi-metadatabase`, `owi-metadatabase-results` |
| Analysis class | `LifetimeDesignFrequencies` |

### 2.0 — Lifetime Design Verification

**`2.0.lifetime-design-verification.ipynb`**

Reads the verification sheet from the same workbook, builds time-series result rows
per turbine and metric, uploads them, retrieves the persisted data, and renders
time-series charts with a metric dropdown.

| Sections | Resolve Metadata · Load Workbook · Build & Upload · Retrieve · Plot |
|---|---|
| Source data | `data/results-example-data.xlsx` |
| SDK packages | `owi-metadatabase`, `owi-metadatabase-results` |
| Analysis class | `LifetimeDesignVerification` |

### 3.0 — Wind Speed Histogram

**`3.0.wind-speed-histogram.ipynb`**

Reads the histogram sheet from the workbook, parses bin labels that start with `[`,
builds one series per title and scope, uploads them, retrieves the persisted rows,
and plots histogram bar charts.

| Sections | Resolve Metadata · Load Workbook · Build & Upload · Retrieve · Plot |
|---|---|
| Source data | `data/results-example-data.xlsx` |
| SDK packages | `owi-metadatabase`, `owi-metadatabase-results` |
| Analysis class | `WindSpeedHistogram` |

### 4.0 — CEIT Corrosion Monitoring (Signal History)

**`4.0.ceit-corrosion-monitoring.ipynb`**

Loads CEIT sensor measurements from a JSON file, matches each sensor code to one SHM
signal through the `SignalHistory` table, uploads corrosion monitoring result series,
retrieves the persisted data, and plots interactive charts with a sensor dropdown.

| Sections | Resolve Metadata · Load Measurements · Match Sensors (SignalHistory) · Build & Upload · Retrieve · Plot |
|---|---|
| Source data | `data/MeasFile_24sea.json` |
| SDK packages | `owi-metadatabase`, `owi-metadatabase-results`, `owi-metadatabase-shm` |
| Analysis class | `CorrosionMonitoring` |

### 4.1 — CEIT Corrosion Monitoring (Simplified)

**`4.1.ceit-corrosion-monitoring-simplified.ipynb`**

Same CEIT workflow as 4.0 but uses a simplified sensor matching strategy based on
`serial_number` containment instead of the `SignalHistory` lookup. Preferred for
environments where the SHM signal history table is not fully populated.

| Sections | Resolve Metadata · Load Measurements · Match Sensors (serial number) · Build & Upload · Retrieve · Plot |
|---|---|
| Source data | `data/MeasFile_24sea.json` |
| SDK packages | `owi-metadatabase`, `owi-metadatabase-results`, `owi-metadatabase-shm` |
| Analysis class | `CorrosionMonitoring` |

## Runtime Controls

Every notebook exposes two boolean flags:

| Flag | Effect |
|---|---|
| `CREATE_NEW_ANALYSIS = True` | Create a new analysis row for the configured timestamp. |
| `CREATE_NEW_ANALYSIS = False` | Reuse the existing analysis found for `ANALYSIS_TIMESTAMP`. |
| `UPLOAD_RESULTS = True` | Create missing result rows or patch existing ones. |
| `UPLOAD_RESULTS = False` | Skip writes and only inspect the selected analysis. |

## Data Files

| File | Format | Used by |
|---|---|---|
| `data/results-example-data.xlsx` | Excel workbook with frequency, verification, and histogram sheets | 1.0, 2.0, 3.0 |
| `data/MeasFile_24sea.json` | CEIT JSON measurement export | 4.0, 4.1 |

## Environment

Authenticated examples use the `OWI_METADATABASE_API_TOKEN` environment variable.

Typical shell setup:

```bash
source ~/.zshrc
export OWI_METADATABASE_API_TOKEN="$OWI_METADATABASE_API_TOKEN"
```

If your shell does not propagate the token into `uv run`, prefix the command with `env OWI_METADATABASE_API_TOKEN="$OWI_METADATABASE_API_TOKEN"`.

## Working With The Notebooks

Open any `.ipynb` file in VS Code and select the project kernel.

Suggested order:

1. `1.0.lifetime-design-frequencies.ipynb`
2. `2.0.lifetime-design-verification.ipynb`
3. `3.0.wind-speed-histogram.ipynb`
4. `4.1.ceit-corrosion-monitoring-simplified.ipynb` (or `4.0` for the SignalHistory variant)

The notebooks are structured so they can run in dry-run mode when the token is missing.
