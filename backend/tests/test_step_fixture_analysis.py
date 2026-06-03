from pathlib import Path

import pytest

from scripts.validate_cad_stack import analyze_step_file


FIXTURE_DIR = Path(__file__).parent / "fixtures"
STEP_EXTENSIONS = {".step", ".stp"}


def _step_fixtures() -> list[Path]:
    return sorted(
        path
        for path in FIXTURE_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in STEP_EXTENSIONS
    )


def test_real_step_fixtures_are_analyzed_when_present() -> None:
    fixtures = _step_fixtures()
    if not fixtures:
        pytest.skip("No real STEP fixtures are present yet.")

    for fixture in fixtures:
        analysis = analyze_step_file(fixture)

        assert analysis["schema_version"] == "1.0"
        assert analysis["diagnostics"]["root_count"] > 0
        assert analysis["diagnostics"]["transferred_count"] > 0
        assert analysis["diagnostics"]["shape_count"] > 0
        assert analysis["diagnostics"]["canonical_unit"]
        assert analysis["topology"]["faces"] > 0
        assert analysis["bounding_box"]["size"][0] > 0
        assert analysis["bounding_box"]["size"][1] > 0
        assert analysis["bounding_box"]["size"][2] > 0
        assert analysis["mass_properties"]["surface_area"] >= 0
        assert analysis["mass_properties"]["volume"] >= 0
