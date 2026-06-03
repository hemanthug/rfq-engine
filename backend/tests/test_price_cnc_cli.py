from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.schemas.pricing import CncPricingResult
from test_feature_extraction import _make_box_shape, _write_step


def test_price_cnc_cli_runs_with_defaults(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(60.0, 40.0, 20.0))

    result = subprocess.run(
        [sys.executable, "scripts/price_cnc.py", str(step_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "CNC budgetary quote:" in result.stdout
    assert "Subtotal:" in result.stdout


def test_price_cnc_cli_json_output_parses(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(60.0, 40.0, 20.0))

    result = subprocess.run(
        [
            sys.executable,
            "scripts/price_cnc.py",
            str(step_path),
            "--material",
            "aluminum_6061",
            "--quantity",
            "5",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    parsed = CncPricingResult.model_validate(json.loads(result.stdout))
    assert parsed.quantity == 5
    assert parsed.request.material == "aluminum_6061"


def test_price_cnc_cli_invalid_material_exits_nonzero(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(60.0, 40.0, 20.0))

    result = subprocess.run(
        [sys.executable, "scripts/price_cnc.py", str(step_path), "--material", "titanium"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "pricing_input_invalid" in result.stderr
