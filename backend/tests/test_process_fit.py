from pathlib import Path

import pytest

from app.cad.feature_extractor import FeatureExtractor
from app.services.process_fit import ProcessFitRecommender
from test_feature_extraction import _make_box_shape, _write_step


def _features(path: Path):
    return FeatureExtractor().extract_from_path(str(path))


def _score_by_process(result):
    return {item.process: item.score for item in result.ranked_processes}


def test_process_fit_returns_ranked_processes_for_generated_box(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(60.0, 40.0, 25.0))

    result = ProcessFitRecommender().recommend(_features(step_path))

    assert result.recommended_process == "cnc"
    assert {item.process for item in result.ranked_processes} == {"cnc", "sheet_metal"}
    assert result.ranked_processes[0].score >= result.ranked_processes[-1].score
    assert result.signals["projected_area_cm2"] > 0


def test_sheet_like_generated_part_ranks_sheet_metal_highest(tmp_path: Path) -> None:
    step_path = tmp_path / "thin_panel.step"
    _write_step(step_path, _make_box_shape(160.0, 90.0, 2.0))

    result = ProcessFitRecommender().recommend(_features(step_path))

    assert result.recommended_process == "sheet_metal"
    assert _score_by_process(result)["sheet_metal"] > _score_by_process(result)["cnc"]


def test_complex_small_profile_part_defaults_to_cnc() -> None:
    step_path = Path(__file__).parent / "fixtures" / "HTD5M-20W-48Z-D20.STEP"

    result = ProcessFitRecommender().recommend(_features(step_path), quantity=1)

    assert result.recommended_process == "cnc"


def test_apcd_sheet_metal_regression_recommends_sheet_metal() -> None:
    step_path = Path(__file__).parent / "fixtures" / "apcd-816.stp"

    result = ProcessFitRecommender().recommend(_features(step_path), quantity=1)

    assert result.recommended_process == "sheet_metal"
    assert result.signals["estimated_thickness_mm"] == pytest.approx(2.46, abs=0.05)
    assert result.signals["bend_candidate_count"] == 8
    assert result.signals["flat_pattern_area_cm2"] > 0


def test_apcd_824_sheet_metal_regression_recommends_sheet_metal() -> None:
    step_path = Path(__file__).parent / "fixtures" / "apcd-824.stp"

    result = ProcessFitRecommender().recommend(_features(step_path), quantity=1)

    assert result.recommended_process == "sheet_metal"
    assert result.signals["estimated_thickness_mm"] == pytest.approx(2.33, abs=0.05)
    assert result.signals["bend_candidate_count"] == 4
    assert result.signals["flat_pattern_area_cm2"] > 0
