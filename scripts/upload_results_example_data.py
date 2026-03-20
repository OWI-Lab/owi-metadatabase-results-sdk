"""Upload or dry-run the example workbook data against the OWI metadatabase dev server."""

from __future__ import annotations

import argparse
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from owi.metadatabase.locations.io import LocationsAPI
from owi.metadatabase.results import (
    AnalysisDefinition,
    LifetimeDesignFrequencies,
    LifetimeDesignVerification,
    WindSpeedHistogram,
    ResultsAPI,
)
from owi.metadatabase.results.serializers import DjangoAnalysisSerializer, DjangoResultSerializer

DEFAULT_BASE_URL = "https://owimetadatabase-dev.azurewebsites.net/api/v1"
DEFAULT_WORKBOOK = Path(__file__).resolve().parent / "data" / "results-example-data.xlsx"
TOKEN_ENV_VAR = "OWI_METADATABASE_API_TOKEN"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--projectsite", default="Belwind")
    parser.add_argument("--upload", action="store_true", help="Attempt live upload when credentials are available.")
    return parser


def render_summary(console: Console, title: str, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    table = Table(title=title)
    if not rows:
        console.print(Panel("No rows", title=title, expand=False))
        return
    for column in rows[0].keys():
        table.add_column(str(column))
    for row in rows:
        table.add_row(*[str(row[column]) for column in rows[0].keys()])
    console.print(table)


def resolve_site_and_locations(
    console: Console,
    api_root: str,
    token: str | None,
    projectsite: str,
    turbines: set[str],
    live: bool,
) -> tuple[int, dict[str, int | None]]:
    if not live or token is None:
        console.print("[yellow]Using dry-run placeholder ids for site and locations.[/yellow]")
        return 1, {turbine: None for turbine in turbines}
    locations_api = LocationsAPI(api_root=api_root, token=token)
    site_id = int(locations_api.get_projectsite_detail(projectsite=projectsite)["id"])
    assetlocations = locations_api.get_assetlocations(projectsite=projectsite)["data"]
    resolved_locations = {
        str(row["title"]): int(row["id"])
        for row in assetlocations.to_dict(orient="records")
        if row.get("title") is not None and row.get("id") is not None
    }
    mapping = {turbine: resolved_locations.get(turbine) for turbine in sorted(turbines)}
    render_summary(
        console,
        "Resolved location ids",
        [{"turbine": turbine, "location_id": mapping[turbine]} for turbine in sorted(mapping)],
    )
    return site_id, mapping


def parse_histogram_sheet(
    path: Path,
    site_id: int,
    location_map: dict[str, int | None],
) -> tuple[AnalysisDefinition, list[dict[str, Any]]]:
    frame = pd.read_excel(path, sheet_name="Lifetime - Wind Histogram", header=1)
    bin_columns = [column for column in frame.columns if isinstance(column, str) and column.startswith("[")]
    series: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        scope = str(row["Scope"])
        location_id = location_map.get(scope)
        parsed_bins = []
        for column in bin_columns:
            left, right = column.removeprefix("[").removesuffix("[").split(",")
            parsed_bins.append((float(left), float(right)))
        series.append(
            {
                "title": row["Title"],
                "description": row["Description"],
                "scope_label": scope,
                "site_id": site_id,
                "location_id": location_id,
                "bins": parsed_bins,
                "values": [float(row[column]) for column in bin_columns],
                "metadata": {"scope_label": scope},
            }
        )
    analysis = AnalysisDefinition(
        name="Lifetime Wind Histogram",
        source_type="excel",
        description="Workbook upload for the lifetime wind histogram example sheet.",
        additional_data={"sheet_name": "Lifetime - Wind Histogram"},
    )
    return analysis, WindSpeedHistogram().to_results({"series": series})


def parse_verification_sheet(
    path: Path,
    site_id: int,
    location_map: dict[str, int | None],
) -> tuple[AnalysisDefinition, list[dict[str, Any]]]:
    frame = pd.read_excel(path, sheet_name="Lifetime -  Design verification")
    rows = []
    for row in frame.to_dict(orient="records"):
        turbine = str(row["Turbine"])
        rows.append(
            {
                "timestamp": row["timestamp"],
                "turbine": turbine,
                "FA1": row.get("FA1 (Hz)"),
                "SS1": row.get("SS1 (Hz)"),
                "SS2": row.get("SS2 (Hz)"),
                "FA2": row.get("FA2 (Hz)"),
                "site_id": site_id,
                "location_id": location_map.get(turbine),
            }
        )
    analysis = AnalysisDefinition(
        name="Lifetime Design Verification",
        source_type="excel",
        description="Workbook upload for the lifetime design verification sheet.",
        additional_data={"sheet_name": "Lifetime -  Design verification"},
    )
    return analysis, LifetimeDesignVerification().to_results({"rows": rows})


def parse_frequencies_sheet(
    path: Path,
    site_id: int,
    location_map: dict[str, int | None],
) -> tuple[AnalysisDefinition, list[dict[str, Any]]]:
    frame = pd.read_excel(path, sheet_name="Lifetime -  Design frequencies")
    rows = []
    for row in frame.to_dict(orient="records"):
        turbine = str(row["Turbine"])
        rows.append(
            {
                "turbine": turbine,
                "reference": row["Reference"],
                "FA1": row.get("FA1 [Hz]"),
                "SS1": row.get("SS1 [Hz]"),
                "FA2": row.get("FA2 [Hz]"),
                "SS2": row.get("SS2 [Hz]"),
                "site_id": site_id,
                "location_id": location_map.get(turbine),
            }
        )
    analysis = AnalysisDefinition(
        name="Lifetime Design Frequencies",
        source_type="excel",
        description="Workbook upload for the lifetime design frequencies sheet.",
        additional_data={"sheet_name": "Lifetime -  Design frequencies"},
    )
    return analysis, LifetimeDesignFrequencies().to_results({"rows": rows})


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    console = Console()
    token = os.getenv(TOKEN_ENV_VAR)
    live_upload = args.upload and token is not None
    if args.upload and token is None:
        console.print(f"[yellow]{TOKEN_ENV_VAR} is not set. Falling back to dry-run mode.[/yellow]")

    workbook = args.workbook
    if not workbook.exists():
        console.print(f"[red]Workbook not found: {workbook}[/red]")
        return 1

    verification_frame = pd.read_excel(workbook, sheet_name="Lifetime -  Design verification")
    frequencies_frame = pd.read_excel(workbook, sheet_name="Lifetime -  Design frequencies")
    turbines = set(verification_frame["Turbine"].astype(str)) | set(frequencies_frame["Turbine"].astype(str))
    site_id, location_map = resolve_site_and_locations(
        console,
        args.base_url,
        token,
        args.projectsite,
        turbines,
        live_upload,
    )

    payload_sets = [
        parse_histogram_sheet(workbook, site_id, location_map),
        parse_verification_sheet(workbook, site_id, location_map),
        parse_frequencies_sheet(workbook, site_id, location_map),
    ]
    analysis_serializer = DjangoAnalysisSerializer()
    result_serializer = DjangoResultSerializer()
    api = ResultsAPI(api_root=args.base_url, token=token) if live_upload else None

    summary_rows: list[dict[str, Any]] = []
    for analysis_definition, result_series in payload_sets:
        summary_rows.append(
            {
                "analysis": analysis_definition.name,
                "results": len(result_series),
                "sheet": analysis_definition.additional_data["sheet_name"],
            }
        )
    render_summary(console, "Workbook upload plan", summary_rows)

    if not live_upload:
        preview_rows = []
        for analysis_definition, result_series in payload_sets:
            preview_rows.append(
                {
                    "analysis": analysis_definition.name,
                    "first_result": result_series[0].short_description,
                    "vector_count": len(result_series[0].vectors),
                }
            )
        render_summary(console, "Dry-run preview", preview_rows)
        console.print("[green]Workbook parsing and payload generation completed successfully.[/green]")
        return 0

    assert api is not None
    for analysis_definition, result_series in payload_sets:
        result_payloads = [result_serializer.to_payload(item, analysis_id=0) for item in result_series]
        invalid_payloads = [payload for payload in result_payloads if payload.get("location") is None]
        valid_payloads = [payload for payload in result_payloads if payload.get("location") is not None]

        if invalid_payloads:
            render_summary(
                console,
                f"Skipped results for {analysis_definition.name}",
                [
                    {
                        "short_description": payload["short_description"],
                        "reason": "backend requires location",
                    }
                    for payload in invalid_payloads
                ],
            )

        if not valid_payloads:
            console.print(
                f"[yellow]Skipping analysis {analysis_definition.name}: no results could be mapped to backend locations.[/yellow]"
            )
            continue

        created_analysis = api.create_analysis(analysis_serializer.to_payload(analysis_definition))
        analysis_id = int(created_analysis["id"])
        upload_payloads = [{**payload, "analysis": analysis_id} for payload in valid_payloads]
        response = api.create_results_bulk(upload_payloads)
        console.print(
            f"[green]Uploaded {len(upload_payloads)} results for analysis {analysis_definition.name}. "
            f"exists={response['exists']}[/green]"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())