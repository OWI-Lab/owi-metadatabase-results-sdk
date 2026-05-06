"""Tests for the combined frequency and verification comparison plot."""

from __future__ import annotations

import pandas as pd
import pytest

from owi.metadatabase.results.plotting.frequency_verification import (
    plot_frequency_verification_asset_history,
    plot_frequency_verification_comparison,
)


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


def _sample_asset_frequency_verification_frame() -> pd.DataFrame:
    frame = _sample_frequency_verification_frame()
    return frame[frame["asset"] == "WFA03"].reset_index(drop=True)


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
        assert verification_series["itemStyle"]["color"] == "#000000"

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
        assert "Source:" in verification_series["tooltip"]["formatter"]
        assert ">link</a>" in verification_series["tooltip"]["formatter"]
        assert "/^https?" not in response.chart.dump_options()
        assert "if (sourceText)" in response.chart.dump_options()

    def test_verification_hover_carries_parent_analysis_source_url(self) -> None:
        frame = _sample_frequency_verification_frame()
        frame.loc[frame["timestamp_label"].notna(), "source_url"] = "https://example.test/source"

        response = plot_frequency_verification_comparison(frame)
        assert response.frontend_spec is not None
        fa1_chart = response.frontend_spec["options_by_key"]["FA1"]
        verification_series = next(series for series in fa1_chart["series"] if series["name"] == "Verification")

        assert verification_series["tooltip"]["enterable"] is True
        assert {point["value"][4] for point in verification_series["data"]} == {"https://example.test/source"}

    def test_result_level_permissable_frequency_adds_red_band(self) -> None:
        frame = _sample_frequency_verification_frame()
        frame.loc[frame["timestamp_label"].notna(), "result_permissable_frequency_lower"] = 1.7
        frame.loc[frame["timestamp_label"].notna(), "result_permissable_frequency_upper"] = 2.8

        response = plot_frequency_verification_comparison(frame)
        assert response.frontend_spec is not None
        fa1_chart = response.frontend_spec["options_by_key"]["FA1"]

        reference_series = next(series for series in fa1_chart["series"] if series["name"] == "Ref 1")
        limit_series = next(
            series for series in fa1_chart["series"] if series["name"] == "_Permissable Frequency Limits"
        )

        assert fa1_chart["legend"][0]["data"] == ["Ref 1", "Ref 2", "Ref 3"]
        assert reference_series["markArea"]["data"] == [[{"yAxis": 1.7}, {"yAxis": 2.8}]]
        assert reference_series["markArea"]["itemStyle"]["color"] == "#d62728"
        assert reference_series["markArea"]["itemStyle"]["opacity"] == pytest.approx(0.35)
        assert limit_series["type"] == "scatter"
        assert limit_series["symbolSize"] == 0
        assert limit_series["itemStyle"]["opacity"] == 0
        assert [point["value"][1] for point in limit_series["data"]] == [1.7, 2.8, 1.7, 2.8]
        assert "min" not in fa1_chart["yAxis"][0]
        assert "max" not in fa1_chart["yAxis"][0]

    def test_result_level_permissable_frequency_uses_asset_limits_and_metric_fallback(self) -> None:
        frame = _sample_frequency_verification_frame()
        verification_mask = frame["timestamp_label"].notna()
        frame.loc[verification_mask & (frame["asset"] == "WFA03"), "result_permissable_frequency_lower"] = 1.7
        frame.loc[verification_mask & (frame["asset"] == "WFA03"), "result_permissable_frequency_upper"] = 2.8
        frame.loc[verification_mask & (frame["asset"] == "WFB07"), "result_permissable_frequency_lower"] = 1.6
        frame.loc[verification_mask & (frame["asset"] == "WFB07"), "result_permissable_frequency_upper"] = 2.5
        frame = pd.concat(
            [
                frame,
                pd.DataFrame(
                    [
                        {
                            "asset": "WFC09",
                            "metric": "fa1",
                            "y": 2.1122,
                            "timestamp_label": "2024-01-11T00:00:00+00:00",
                            "hover_name": "WFC09",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

        response = plot_frequency_verification_comparison(frame)
        assert response.frontend_spec is not None
        fa1_chart = response.frontend_spec["options_by_key"]["FA1"]
        lower_series = next(
            series for series in fa1_chart["series"] if series["name"] == "_Permissable Frequency Lower"
        )
        band_series = next(series for series in fa1_chart["series"] if series["name"] == "Permissable Frequency Band")

        assert fa1_chart["xAxis"][0]["data"] == ["WFA03", "WFB07", "WFC09"]
        assert lower_series["data"] == pytest.approx([1.7, 1.6, 1.6])
        assert band_series["data"] == pytest.approx([1.1, 0.9, 1.2])

    def test_analysis_level_permissable_frequency_is_used_when_result_level_missing(self) -> None:
        frame = _sample_frequency_verification_frame()
        frame.loc[frame["timestamp_label"].notna(), "analysis_permissable_frequency_lower"] = 1.4
        frame.loc[frame["timestamp_label"].notna(), "analysis_permissable_frequency_upper"] = 2.9

        response = plot_frequency_verification_comparison(frame)
        assert response.frontend_spec is not None
        fa1_chart = response.frontend_spec["options_by_key"]["FA1"]
        reference_series = next(series for series in fa1_chart["series"] if series["name"] == "Ref 1")
        limit_series = next(
            series for series in fa1_chart["series"] if series["name"] == "_Permissable Frequency Limits"
        )

        assert reference_series["markArea"]["data"] == [[{"yAxis": 1.4}, {"yAxis": 2.9}]]
        assert [point["value"][1] for point in limit_series["data"]] == [1.4, 2.9, 1.4, 2.9]


class TestFrequencyVerificationAssetHistoryPlot:
    def test_returns_metric_dropdown_without_asset_dropdown(self) -> None:
        response = plot_frequency_verification_asset_history(_sample_asset_frequency_verification_frame())

        assert response.frontend_spec is not None
        assert response.frontend_spec["mode"] == "dropdown"
        assert len(response.frontend_spec["controls"]) == 1
        assert response.frontend_spec["controls"][0]["label"] == "Metric"
        assert set(response.frontend_spec["options_by_key"]) == {"FA1"}

    def test_uses_datetime_axis_ordered_oldest_to_newest(self) -> None:
        response = plot_frequency_verification_asset_history(_sample_asset_frequency_verification_frame())
        assert response.frontend_spec is not None
        fa1_chart = response.frontend_spec["options_by_key"]["FA1"]

        assert fa1_chart["xAxis"][0]["data"] == [
            "2024-01-01T00:00:00+00:00",
            "2024-01-10T00:00:00+00:00",
        ]
        assert fa1_chart["xAxis"][0]["name"] == "Datetime"
        assert fa1_chart["xAxis"][0]["boundaryGap"] is True
        assert fa1_chart["xAxis"][0]["axisLabel"]["rotate"] == 0

    def test_frequency_series_are_dashed_horizontal_levels_with_fleetwide_colors(self) -> None:
        response = plot_frequency_verification_asset_history(_sample_asset_frequency_verification_frame())
        assert response.frontend_spec is not None
        fa1_chart = response.frontend_spec["options_by_key"]["FA1"]

        assert fa1_chart["legend"][0]["data"] == ["Ref 1", "Ref 2", "Ref 3"]
        reference_series = next(series for series in fa1_chart["series"] if series["name"] == "Ref 1")

        assert reference_series["type"] == "line"
        assert reference_series["lineStyle"]["type"] == "dashed"
        assert reference_series["lineStyle"]["color"] == "#1f77b4"
        assert [point[0] for point in reference_series["data"]] == [
            "2024-01-01T00:00:00+00:00",
            "2024-01-10T00:00:00+00:00",
        ]
        assert [point[1] for point in reference_series["data"]] == [2.4123, 2.4123]

    def test_verification_series_keeps_marker_style_without_opacity_scaling(self) -> None:
        response = plot_frequency_verification_asset_history(_sample_asset_frequency_verification_frame())
        assert response.frontend_spec is not None
        fa1_chart = response.frontend_spec["options_by_key"]["FA1"]

        verification_series = next(series for series in fa1_chart["series"] if series["name"] == "Verification")
        opacities = [point["itemStyle"]["opacity"] for point in verification_series["data"]]

        assert verification_series["type"] == "scatter"
        assert verification_series["symbolSize"] == 8
        assert verification_series["itemStyle"]["color"] == "#000000"
        assert opacities == [1.0, 1.0]

    def test_verification_hover_keeps_asset_frequency_and_timestamp_content(self) -> None:
        response = plot_frequency_verification_asset_history(_sample_asset_frequency_verification_frame())
        assert response.frontend_spec is not None
        fa1_chart = response.frontend_spec["options_by_key"]["FA1"]
        verification_series = next(series for series in fa1_chart["series"] if series["name"] == "Verification")

        assert "<strong>' + value[2] + '</strong>'" in verification_series["tooltip"]["formatter"]
        assert "Frequency:" in verification_series["tooltip"]["formatter"]
        assert "Timestamp:" in verification_series["tooltip"]["formatter"]
        assert "Source:" in verification_series["tooltip"]["formatter"]
        assert ">link</a>" in verification_series["tooltip"]["formatter"]
        assert "/^https?" not in response.chart.dump_options()
        assert "if (sourceText)" in response.chart.dump_options()

    def test_asset_history_renders_permissable_frequency_band(self) -> None:
        frame = _sample_asset_frequency_verification_frame()
        frame.loc[frame["timestamp_label"].notna(), "result_permissable_frequency_lower"] = 1.7
        frame.loc[frame["timestamp_label"].notna(), "result_permissable_frequency_upper"] = 2.8

        response = plot_frequency_verification_asset_history(frame)
        assert response.frontend_spec is not None
        fa1_chart = response.frontend_spec["options_by_key"]["FA1"]

        reference_series = next(series for series in fa1_chart["series"] if series["name"] == "Ref 1")
        limit_series = next(
            series for series in fa1_chart["series"] if series["name"] == "_Permissable Frequency Limits"
        )

        assert reference_series["markArea"]["data"] == [[{"yAxis": 1.7}, {"yAxis": 2.8}]]
        assert [point["value"][1] for point in limit_series["data"]] == [1.7, 2.8, 1.7, 2.8]
        assert "min" not in fa1_chart["yAxis"][0]
        assert "max" not in fa1_chart["yAxis"][0]

    def test_requires_single_asset_after_filtering(self) -> None:
        with pytest.raises(ValueError, match="expects data for one asset"):
            plot_frequency_verification_asset_history(_sample_frequency_verification_frame())
