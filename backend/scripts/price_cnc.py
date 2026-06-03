"""Generate a research-informed budgetary 3-axis CNC milling quote for a STEP file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.cad.feature_extractor import FeatureExtractor
from app.pricing.cnc import CncBudgetaryPricer
from app.pricing.errors import PricingError
from app.schemas.pricing import CncPricingRequest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step_file", help="Real STEP file to price")
    parser.add_argument("--material", default="aluminum_6061", help="Rate-card material id")
    parser.add_argument("--quantity", type=int, default=1, help="Positive part quantity")
    parser.add_argument("--tolerance", default="standard", help="Tolerance class")
    parser.add_argument("--finish", default="as_machined", help="Finish id")
    parser.add_argument("--lead-time", default="standard", help="Lead-time class")
    parser.add_argument("--json", action="store_true", help="Emit full JSON output")
    args = parser.parse_args(argv)

    try:
        request = CncPricingRequest(
            material=args.material,
            quantity=args.quantity,
            tolerance_class=args.tolerance,
            finish=args.finish,
            lead_time_class=args.lead_time,
        )
        features = FeatureExtractor().extract_from_path(args.step_file)
        result = CncBudgetaryPricer().price(features, request)
    except PricingError as exc:
        print(json.dumps(exc.as_dict(), indent=2), file=sys.stderr)
        return 2
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(result.model_dump_json(indent=2))
        return 0

    print(f"CNC budgetary quote: {result.source.source.file.source_path}")
    print(f"  Process: {result.process}")
    print(f"  Material: {result.request.material}")
    print(f"  Quantity: {result.quantity}")
    print(f"  Subtotal: {result.currency} {result.subtotal:.2f}")
    print(f"  Unit price: {result.currency} {result.unit_price:.2f}")
    print(f"  Confidence: {result.confidence:.2f}")
    print("  Line items:")
    for item in result.line_items:
        print(f"    - {item.code}: {result.currency} {item.amount:.2f} ({item.basis})")
    print(f"  Warnings: {result.warnings}")
    print(f"  Assumptions: {result.assumptions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
