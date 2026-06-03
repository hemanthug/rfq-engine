from scripts.validate_cad_stack import collect_environment_report


def test_pythonocc_imports_and_reports_environment() -> None:
    report = collect_environment_report()

    assert report["python"].startswith("3.10.")
    assert report["pythonocc_version"] != "unknown"
    assert report["occ_module"] != "unknown"

