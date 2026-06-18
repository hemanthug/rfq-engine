"""Extract conservative manufacturing-oriented feature candidates from STEP files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.cad.feature_extractor import FeatureExtractor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step_file", help="Real STEP file to analyze")
    parser.add_argument("--json", action="store_true", help="Emit full JSON output")
    args = parser.parse_args(argv)

    result = FeatureExtractor().extract_from_path(args.step_file)
    if args.json:
        print(result.model_dump_json(indent=2))
        return 0

    print(f"Feature extraction: {result.source.file.source_path}")
    print(f"  Faces: {len(result.faces)}")
    print(f"  Edges: {len(result.edges)}")
    print(f"  Adjacency edges: {len(result.adjacency)}")
    print(f"  Hole candidates: {len(result.holes)}")
    print(f"  Pocket candidates: {len(result.pockets)}")
    print(f"  Complexity score: {result.complexity.score}")
    print(f"  Deferred feature types: {result.diagnostics.deferred_feature_types}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

