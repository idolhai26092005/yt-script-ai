"""Lightweight backend import-boundary checker.

Run from repository root:
    backend/venv/bin/python backend/scripts/check_import_boundaries.py
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "app"

FORBIDDEN_PREFIXES = {
    "app.models": ("app.api", "app.services", "app.crud"),
    "app.crud": ("app.api",),
    "app.services.production": ("app.api",),
    "app.core": ("app.api",),
}


# Boundary guard: import extraction uses AST so review can check architecture
# direction without importing modules or triggering runtime side effects.
def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


# Boundary guard: module names mirror package paths under backend/app so rules
# stay independent of the current working directory.
def module_name(path: Path) -> str:
    relative = path.relative_to(ROOT).with_suffix("")
    return ".".join(relative.parts)


# Boundary guard: the first checker blocks only import directions that should
# already be invalid, leaving endpoint-thinning work to later OpenSpec tasks.
def boundary_violations() -> list[str]:
    violations: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        source_module = module_name(path)
        imports = imported_modules(path)
        for source_prefix, forbidden_prefixes in FORBIDDEN_PREFIXES.items():
            if not source_module.startswith(source_prefix):
                continue
            for imported in imports:
                if any(imported == prefix or imported.startswith(prefix + ".") for prefix in forbidden_prefixes):
                    violations.append(f"{source_module} imports forbidden module {imported}")
    return violations


# CLI guard: return non-zero only when a hard import boundary is violated, making
# the script usable by CI later without changing runtime behavior now.
def main() -> int:
    violations = boundary_violations()
    if violations:
        for violation in violations:
            print(violation)
        return 1
    print("backend import boundaries ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

