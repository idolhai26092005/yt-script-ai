from pathlib import Path

from scripts import check_dead_code
from scripts.check_dead_code import (
    INTENTIONAL_UNREFERENCED_MODULES,
    IntentionalUnreferencedModule,
    find_dead_code_violations,
)


# Dead-code guard test mirrors the standalone checker so CI catches reintroduced
# modules that previous cleanup proved unused.
def test_removed_backend_modules_stay_removed():
    backend_root = Path(__file__).resolve().parents[2]

    assert find_dead_code_violations(backend_root) == []


# Source-audit guard test proves the checker fails new app modules that are not
# imported internally and not documented as intentional scaffolds.
def test_unreferenced_app_module_without_allowlist_reason_fails(tmp_path, monkeypatch):
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "__init__.py").write_text("", encoding="utf-8")
    (app_root / "entrypoint.py").write_text("import app.used\n", encoding="utf-8")
    (app_root / "used.py").write_text("VALUE = 1\n", encoding="utf-8")
    (app_root / "orphan.py").write_text("VALUE = 2\n", encoding="utf-8")
    monkeypatch.setattr(
        check_dead_code,
        "INTENTIONAL_UNREFERENCED_MODULES",
        (
            IntentionalUnreferencedModule(
                "app.entrypoint",
                "app/entrypoint.py",
                "Synthetic entrypoint for dead-code checker test.",
            ),
        ),
    )

    violations = find_dead_code_violations(tmp_path)

    assert any("app/orphan.py" in violation for violation in violations)
    assert not any("app/entrypoint.py" in violation for violation in violations)


# Allowlist reason guard keeps every retained unreferenced source module tied to
# an explicit contract instead of an unexplained permanent exception.
def test_intentional_unreferenced_modules_have_reasons():
    assert INTENTIONAL_UNREFERENCED_MODULES
    assert all(entry.reason.strip() for entry in INTENTIONAL_UNREFERENCED_MODULES)
