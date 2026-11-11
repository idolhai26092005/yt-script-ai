from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RemovedModule:
    module: str
    path: str


# Source-audit allowlist entry keeps retained scaffolds tied to a concrete
# removal or wiring rationale instead of a silent exception.
@dataclass(frozen=True)
class IntentionalUnreferencedModule:
    module: str
    path: str
    reason: str


REMOVED_MODULES = (
    RemovedModule("app.core.prompts", "app/core/prompts.py"),
    RemovedModule("app.crud.script_cache", "app/crud/script_cache.py"),
)

INTENTIONAL_UNREFERENCED_MODULES = (
    IntentionalUnreferencedModule(
        "app.api.v1.router",
        "app/api/v1/router.py",
        "FastAPI entrypoint imported from backend/main.py, outside the app package scan.",
    ),
    IntentionalUnreferencedModule(
        "app.services.production.orchestrator",
        "app/services/production/orchestrator.py",
        "RoleGraphRunner scaffold required by backend-production-architecture before producer wiring moves.",
    ),
    IntentionalUnreferencedModule(
        "app.services.production.prompts.catalog",
        "app/services/production/prompts/catalog.py",
        "Prompt catalog contract required by backend-production-architecture before role prompt call sites move.",
    ),
    IntentionalUnreferencedModule(
        "app.services.production.validation.registry",
        "app/services/production/validation/registry.py",
        "Validator registry contract required by backend-production-architecture before producer validation call sites move.",
    ),
)


# Dead-code guard: deleted modules stay listed here with exact paths so future
# cleanups have a cheap check against reviving known-unused import surfaces.
def find_dead_code_violations(backend_root: Path) -> list[str]:
    violations: list[str] = []
    for removed in REMOVED_MODULES:
        removed_path = backend_root / removed.path
        if removed_path.exists():
            violations.append(f"removed module file still exists: {removed_path}")

    violations.extend(_unreferenced_allowlist_violations(backend_root))

    scan_roots = (backend_root / "app", backend_root / "tests", backend_root / "scripts")
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for path in sorted(scan_root.rglob("*.py")):
            if path == Path(__file__).resolve():
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError as exc:
                violations.append(f"cannot parse {path}: {exc}")
                continue
            violations.extend(_import_violations(path, tree))

    return violations


# Source-audit guard: every unreferenced app module must have a reason so
# cleanup cannot silently keep dead scaffolding forever.
def _unreferenced_allowlist_violations(backend_root: Path) -> list[str]:
    allowlist = {entry.module: entry for entry in INTENTIONAL_UNREFERENCED_MODULES}
    violations: list[str] = []
    for entry in INTENTIONAL_UNREFERENCED_MODULES:
        if not entry.reason.strip():
            violations.append(f"intentional unreferenced module lacks reason: {entry.module}")
        if not (backend_root / entry.path).exists():
            violations.append(f"intentional unreferenced module path missing: {entry.path}")

    for module, path in find_unreferenced_app_modules(backend_root).items():
        if module not in allowlist:
            violations.append(f"unreferenced app module lacks allowlist reason: {path}")

    return violations


# Module reachability scan uses AST only; it avoids executing imports that may
# touch settings, databases, or provider clients during cleanup checks.
def find_unreferenced_app_modules(backend_root: Path) -> dict[str, Path]:
    app_root = backend_root / "app"
    modules = {
        _module_name(backend_root, path): path
        for path in sorted(app_root.rglob("*.py"))
        if path.name != "__init__.py"
    }
    referenced: set[str] = set()

    for path in sorted(app_root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        current_module = _module_name(backend_root, path)
        referenced.update(_app_imports(current_module, tree, set(modules)))

    return {
        module: path
        for module, path in modules.items()
        if module not in referenced
    }


# Import guard: catch both `import app.core.prompts` and
# `from app.core.prompts import ...` without executing project code.
def _import_violations(path: Path, tree: ast.AST) -> list[str]:
    violations: list[str] = []
    removed_modules = {removed.module for removed in REMOVED_MODULES}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in removed_modules or any(
                    alias.name.startswith(f"{module}.") for module in removed_modules
                ):
                    violations.append(f"{path} imports removed module {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module in removed_modules or any(
                node.module.startswith(f"{module}.") for module in removed_modules
            ):
                violations.append(f"{path} imports removed module {node.module}")
    return violations


# Import collector resolves package-relative imports and `from package import
# submodule` forms so router-style imports count as real module reachability.
def _app_imports(current_module: str, tree: ast.AST, known_modules: set[str]) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _add_known_import(imports, alias.name, known_modules)
        elif isinstance(node, ast.ImportFrom):
            module = _resolve_import_from(current_module, node)
            if not module:
                continue
            _add_known_import(imports, module, known_modules)
            for alias in node.names:
                if alias.name == "*":
                    continue
                _add_known_import(imports, f"{module}.{alias.name}", known_modules)
    imports.discard(current_module)
    return imports


# Known-module matching keeps the audit module-level; symbol imports from a
# package are ignored unless they identify an actual Python module.
def _add_known_import(imports: set[str], module: str, known_modules: set[str]) -> None:
    if module in known_modules:
        imports.add(module)


# Relative-import resolver mirrors Python package semantics enough for static
# audits without importing the package under test.
def _resolve_import_from(current_module: str, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module

    package_parts = current_module.split(".")[:-1]
    if node.level > len(package_parts) + 1:
        return None
    base_parts = package_parts[: len(package_parts) - node.level + 1]
    if node.module:
        base_parts.extend(node.module.split("."))
    return ".".join(base_parts)


# Path-to-module conversion stays local to backend root so checks work from
# CI, local shells, and moved worktrees.
def _module_name(backend_root: Path, path: Path) -> str:
    return ".".join(path.relative_to(backend_root).with_suffix("").parts)


# CLI guard: CI/local preflight gets concise output and non-zero exit on stale
# deleted module files or imports.
def main() -> int:
    backend_root = Path(__file__).resolve().parents[1]
    violations = find_dead_code_violations(backend_root)
    if violations:
        print("backend dead-code violations:")
        for violation in violations:
            print(f"- {violation}")
        return 1
    print("backend dead-code ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
