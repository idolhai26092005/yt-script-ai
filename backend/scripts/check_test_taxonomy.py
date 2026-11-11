from __future__ import annotations

from pathlib import Path

ALLOWED_TEST_DIRS = {
    "api",
    "contracts",
    "db",
    "regression",
    "services",
    "topics",
}

ALLOWED_SERVICE_DIRS = {
    "gemini",
    "production",
}


# Taxonomy guard: fail fast when new tests bypass the documented behavior
# folders, so future cleanup keeps a searchable test map.
def find_taxonomy_violations(tests_dir: Path) -> list[str]:
    violations: list[str] = []
    if not tests_dir.exists():
        return [f"missing tests directory: {tests_dir}"]

    for path in sorted(tests_dir.glob("test_*.py")):
        violations.append(f"root-level test file is not allowed: {path}")

    for child in sorted(item for item in tests_dir.iterdir() if item.is_dir()):
        if child.name.startswith("__") or child.name == ".pytest_cache":
            continue
        if child.name not in ALLOWED_TEST_DIRS:
            violations.append(f"unknown test taxonomy directory: {child}")

    services_dir = tests_dir / "services"
    if services_dir.exists():
        for child in sorted(item for item in services_dir.iterdir() if item.is_dir()):
            if child.name.startswith("__"):
                continue
            if child.name not in ALLOWED_SERVICE_DIRS:
                violations.append(f"unknown service test taxonomy directory: {child}")

    return violations


# CLI guard: keep script usable in CI and as a local preflight without pytest.
def main() -> int:
    tests_dir = Path(__file__).resolve().parents[1] / "tests"
    violations = find_taxonomy_violations(tests_dir)
    if violations:
        print("backend test taxonomy violations:")
        for violation in violations:
            print(f"- {violation}")
        return 1
    print("backend test taxonomy ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
