import subprocess
import sys
import textwrap


def test_app_startup_and_health_do_not_import_occ() -> None:
    script = textwrap.dedent(
        """
        import sys
        from fastapi.testclient import TestClient
        from app.main import create_app

        client = TestClient(create_app())
        response = client.get("/health/live")
        response.raise_for_status()
        print("OCC" in sys.modules)
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "False"


def test_step_reader_import_does_not_import_occ() -> None:
    script = textwrap.dedent(
        """
        import sys
        from app.cad.step_reader import StepReader

        StepReader
        print("OCC" in sys.modules)
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "False"


def test_feature_schema_import_does_not_import_occ() -> None:
    script = textwrap.dedent(
        """
        import sys
        from app.schemas.features import FeatureExtractionResult

        FeatureExtractionResult
        print("OCC" in sys.modules)
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "False"


def test_pricing_imports_do_not_import_occ() -> None:
    script = textwrap.dedent(
        """
        import sys
        from app.pricing.cnc import CncBudgetaryPricer
        from app.schemas.pricing import CncPricingRequest

        CncBudgetaryPricer
        CncPricingRequest
        print("OCC" in sys.modules)
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "False"
