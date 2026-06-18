"""Validate the OpenCascade/pythonOCC CAD stack against real STEP files."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.cad.step_reader import StepReader


def _import_occ_modules() -> dict[str, Any]:
    import OCC
    from OCC.Core.STEPControl import STEPControl_Reader

    return {
        "OCC": OCC,
        "STEPControl_Reader": STEPControl_Reader,
    }


def collect_environment_report() -> dict[str, Any]:
    modules = _import_occ_modules()
    occ = modules["OCC"]
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pythonocc_version": getattr(occ, "VERSION", "unknown"),
        "occ_module": getattr(occ, "__file__", "unknown"),
    }


def analyze_step_file(path: str | Path) -> dict[str, Any]:
    return StepReader().parse(path).model_dump()


def _print_text_report(report: dict[str, Any], analyses: list[dict[str, Any]]) -> None:
    print("CAD stack environment")
    print(f"  Python: {report['python']}")
    print(f"  Platform: {report['platform']}")
    print(f"  pythonOCC: {report['pythonocc_version']}")
    print(f"  OCC module: {report['occ_module']}")

    if not analyses:
        print("\nNo STEP files supplied. Environment import validation completed.")
        return

    for analysis in analyses:
        print(f"\nSTEP analysis: {analysis['file']['source_path']}")
        print(f"  Valid shape: {analysis['validity']['is_valid']}")
        print(
            "  Roots transferred: "
            f"{analysis['diagnostics']['transferred_count']} / {analysis['diagnostics']['root_count']}"
        )
        print(f"  Shape count: {analysis['diagnostics']['shape_count']}")
        print(f"  Shape kind: {analysis['diagnostics']['shape_kind']}")
        print(f"  Source length units: {analysis['diagnostics']['source_length_units']}")
        print(f"  Canonical unit: {analysis['diagnostics']['canonical_unit']}")
        print(f"  Bounding box size: {analysis['bounding_box']['size']}")
        print(f"  Volume: {analysis['mass_properties']['volume']}")
        print(f"  Surface area: {analysis['mass_properties']['surface_area']}")
        print(f"  Tolerance summary: {analysis['tolerance_summary']}")
        print(f"  Topology: {analysis['topology']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step_files", nargs="*", help="Real STEP files to analyze")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args(argv)

    report = collect_environment_report()
    analyses = [analyze_step_file(path) for path in args.step_files]

    if args.json:
        print(json.dumps({"environment": report, "step_analyses": analyses}, indent=2))
    else:
        _print_text_report(report, analyses)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
