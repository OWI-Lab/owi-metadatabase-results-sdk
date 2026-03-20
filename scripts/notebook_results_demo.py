"""Terminal reimplementation of the legacy results upload notebook."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import os
from typing import Any

from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table

from owi.metadatabase.geometry.io import GeometryAPI
from owi.metadatabase.locations.io import LocationsAPI
from owi.metadatabase.results import AnalysisDefinition, RelatedObject, ResultSeries, ResultVector, ResultsAPI
from owi.metadatabase.results.serializers import DjangoAnalysisSerializer, DjangoResultSerializer

DEFAULT_BASE_URL = "https://owimetadatabase-dev.azurewebsites.net/api/v1"
TOKEN_ENV_VAR = "OWI_METADATABASE_API_TOKEN"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--site", default="Belwind")
    parser.add_argument("--location", default="BBC01")
    parser.add_argument("--analysis-name", default="Example analysis")
    parser.add_argument("--upload", action="store_true", help="Upload to the configured server when credentials exist.")
    return parser


def render_mapping(console: Console, title: str, mapping: dict[str, Any]) -> None:
    console.print(Panel(JSON.from_data(mapping), title=title, expand=False))


def render_table(console: Console, title: str, rows: list[dict[str, Any]]) -> None:
    table = Table(title=title)
    if not rows:
        console.print(Panel("No rows", title=title, expand=False))
        return
    for column in rows[0]:
        table.add_column(str(column))
    for row in rows:
        table.add_row(*[str(row[column]) for column in rows[0]])
    console.print(table)


def resolve_context_ids(console: Console, api_root: str, token: str, site: str, location: str) -> tuple[int | None, int | None, int | None]:
    locations_api = LocationsAPI(api_root=api_root, token=token)
    geometry_api = GeometryAPI(api_root=api_root, token=token)
    site_id = locations_api.get_projectsite_detail(projectsite=site)["id"]
    location_id = locations_api.get_assetlocation_detail(projectsite=site, assetlocation=location)["id"]
    subassemblies = geometry_api.get_subassemblies(projectsite=site, assetlocation=location)["data"]
    subassembly_id = int(subassemblies.loc[0, "id"]) if not subassemblies.empty else None
    render_table(
        console,
        "Resolved context ids",
        [{"site_id": site_id, "location_id": location_id, "subassembly_id": subassembly_id}],
    )
    return site_id, location_id, subassembly_id


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    console = Console()
    token = os.getenv(TOKEN_ENV_VAR)
    upload_enabled = args.upload and token is not None

    console.print(Panel("Legacy results notebook terminal demo", subtitle="owi-metadatabase-results-sdk"))
    if args.upload and token is None:
        console.print(f"[yellow]{TOKEN_ENV_VAR} is not set. Falling back to dry-run mode.[/yellow]")

    site_id = 1
    location_id = None
    related_object = RelatedObject(type="geometry.subassembly", id=1)
    if upload_enabled:
        site_id, location_id, subassembly_id = resolve_context_ids(console, args.base_url, token, args.site, args.location)
        related_object = RelatedObject(type="geometry.subassembly", id=subassembly_id) if subassembly_id else None

    analysis = AnalysisDefinition(
        name=args.analysis_name,
        source_type="script",
        description="Terminal reimplementation of the legacy notebook flow.",
        additional_data={"script": "notebook_results_demo.py", "created_at": datetime.now(UTC).isoformat()},
    )
    x_values = [float(index) for index in range(25)]
    y_values = [float(index) for index in range(25)]
    result_series = ResultSeries(
        analysis_name=args.analysis_name,
        analysis_kind="comparison",
        result_scope="site",
        short_description="test_example_1",
        description="Example data uploaded from the terminal notebook demo.",
        site_id=site_id,
        location_id=location_id,
        related_object=related_object,
        data_additional={"site_name": args.site, "location_name": args.location},
        vectors=[
            ResultVector(name="x", unit="mm", values=x_values),
            ResultVector(name="y", unit="mm", values=y_values),
        ],
    )

    analysis_payload = DjangoAnalysisSerializer().to_payload(analysis)
    render_mapping(console, "Analysis payload", analysis_payload)

    result_payload_preview = result_series.to_record_payload(analysis_id=0)
    render_mapping(console, "Result payload preview", result_payload_preview)

    if not upload_enabled:
        console.print("[green]Dry-run completed successfully.[/green]")
        return 0

    api = ResultsAPI(api_root=args.base_url, token=token)
    created_analysis = api.create_analysis(analysis_payload)
    analysis_id = int(created_analysis["id"])
    console.print(f"[green]Created analysis with id {analysis_id}.[/green]")

    result_payload = DjangoResultSerializer().to_payload(result_series, analysis_id=analysis_id)
    created_result = api.create_result(result_payload)
    console.print(f"[green]Created result with id {created_result['id']}.[/green]")

    retrieved_analysis = created_analysis["data"].to_dict(orient="records")
    try:
        retrieved_result = api.get_results(
            short_description=result_series.short_description,
            analysis=args.analysis_name,
        )["data"].to_dict(orient="records")
    except Exception:
        retrieved_result = created_result["data"].to_dict(orient="records")
    render_table(console, "Retrieved analysis", retrieved_analysis)
    render_table(console, "Retrieved results", retrieved_result[:5])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())