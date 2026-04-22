"""Tests for the combined frequency and verification comparison plot."""

from __future__ import annotations

import pandas as pd
import pytest

from owi.metadatabase.results.plotting.frequency_verification import plot_frequency_verification_comparison


def _sample_frequency_verification_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "asset": "WFB07",
                "metric": "fa1",
                "y": 1.7312,
                "reference_label": "Ref 1",
                "reference_order": 1,
            },
            {
                "asset": "WFB07",
                "metric": "fa1",
                "y": 1.4286,
                "reference_label": "Ref 2",
                "reference_order": 2,
            },
            {
                "asset": "WFB07",
                "metric": "fa1",
                "y": 1.1194,
                "reference_label": "Ref 3",
                "reference_order": 3,
            },
            {
                "asset": "WFA03",
                "metric": "fa1",
                "y": 2.4123,
                "reference_label": "Ref 1",
                "reference_order": 1,
            },
            {
                "asset": "WFA03",
                "metric": "fa1",
                "y": 2.0875,
                "reference_label": "Ref 2",
                "reference_order": 2,
            },
            {
                "asset": "WFA03",
                "metric": "fa1",
                "y": 1.9042,
                "reference_label": "Ref 3",
                "reference_order": 3,
            },
            {
                "asset": "WFA03",
                "metric": "fa1",
                "y": 2.5517,
                "timestamp_label": "2024-01-01T00:00:00+00:00",
                "hover_name": "WFA03",
            },
            {
                "asset": "WFA03",
                "metric": "fa1",
                "y": 2.6631,
                "timestamp_label": "2024-01-10T00:00:00+00:00",
                "hover_name": "WFA03",
            },
            {
                "asset": "WFB07",
                "metric": "fa1",
                "y": 2.2746,
                "timestamp_label": "2024-01-10T00:00:00+00:00",
                "hover_name": "WFB07",
            },
            {
                "asset": "WFA03",
                "metric": "ss1",
                "y": 1.3478,
                "reference_label": "Ref 1",
                "reference_order": 1,
            },
        ]
    )


class TestFrequencyVerificationComparisonPlot:
    def test_empty_data_raises(self) -> None:
        empty = pd.DataFrame(columns=["asset", "metric", "y"])
        with pytest.raises(ValueError, match="No frequency verification data"):
            plot_frequency_verification_comparison(empty)

    def test_returns_metric_dropdown(self) -> None:
        response = plot_frequency_verification_comparison(_sample_frequency_verification_frame())
        assert response.frontend_spec is not None
        assert response.frontend_spec["mode"] == "dropdown"
        assert response.frontend_spec["controls"][0]["label"] == "Metric"
        assert set(response.frontend_spec["options_by_key"]) == {"FA1", "SS1"}

    def test_orders_assets_alphabetically_and_keeps_reference_legend(self) -> None:
        response = plot_frequency_verification_comparison(_sample_frequency_verification_frame())
        assert response.frontend_spec is not None
        fa1_chart = response.frontend_spec["options_by_key"]["FA1"]

        assert fa1_chart["xAxis"][0]["data"] == ["WFA03", "WFB07"]
        assert fa1_chart["legend"][0]["data"] == ["Ref 1", "Ref 2", "Ref 3"]

    def test_verification_series_uses_timestamp_opacity_range(self) -> None:
        response = plot_frequency_verification_comparison(_sample_frequency_verification_frame())
        assert response.frontend_spec is not None
        fa1_chart = response.frontend_spec["options_by_key"]["FA1"]

        verification_series = next(series for series in fa1_chart["series"] if series["name"] == "Verification")
        assert verification_series["type"] == "scatter"
        opacities = [point["itemStyle"]["opacity"] for point in verification_series["data"]]

        assert min(opacities) == pytest.approx(0.3)
        assert max(opacities) == pytest.approx(1.0)

    def test_hides_title_and_applies_marker_styling(self) -> None:
        response = plot_frequency_verification_comparison(_sample_frequency_verification_frame())
        assert response.frontend_spec is not None
        fa1_chart = response.frontend_spec["options_by_key"]["FA1"]

        assert fa1_chart["title"][0]["show"] is False
        assert fa1_chart["grid"]["top"] == "22%"
        assert fa1_chart["xAxis"][0].get("name", "") == ""

        reference_series = next(series for series in fa1_chart["series"] if series["name"] == "Ref 1")
        verification_series = next(series for series in fa1_chart["series"] if series["name"] == "Verification")

        assert reference_series["symbolSize"] == 5
        assert verification_series["symbolSize"] == 8
        assert verification_series["itemStyle"]["color"] == "#d62728"

    def test_uses_custom_tooltips_for_frequency_and_verification(self) -> None:
        response = plot_frequency_verification_comparison(_sample_frequency_verification_frame())
        assert response.frontend_spec is not None
        fa1_chart = response.frontend_spec["options_by_key"]["FA1"]

        reference_series = next(series for series in fa1_chart["series"] if series["name"] == "Ref 1")
        verification_series = next(series for series in fa1_chart["series"] if series["name"] == "Verification")

        assert "params && params.data != null ? params.data : params.value" in reference_series["tooltip"]["formatter"]
        assert "<strong>' + params.name + '</strong>'" in reference_series["tooltip"]["formatter"]
        assert "params.seriesName" in reference_series["tooltip"]["formatter"]
        assert "<strong>' + value[0] + '</strong>'" in verification_series["tooltip"]["formatter"]
        assert "Timestamp:" in verification_series["tooltip"]["formatter"]
