import ast
from pathlib import Path


FORBIDDEN_IMPORT_NAMES = {
    "ProductionService",
    "SERIES_SUGGESTION_PROMPT",
    "SERIES_NEXT_EPISODE_PROMPT",
    "apply_rolling_context_to_suggestion",
}

FORBIDDEN_MODULE_NAMES = {
    "app.api.v1.endpoints.series",
    "app.services.production.context_compressor",
    "app.services.production.prompts.series",
}


# Boundary audit guard: the rebuilt series core may reuse small shared helpers,
# but must not import legacy series orchestration or the single-video facade.
def test_series_v2_core_has_no_forbidden_imports_or_calls():
    service_root = Path(__file__).resolve().parents[2] / "app" / "services" / "series_v2"
    violations: list[str] = []

    for path in sorted(service_root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module in FORBIDDEN_MODULE_NAMES:
                    violations.append(f"{path.name}: forbidden module {module}")
                for alias in node.names:
                    if alias.name in FORBIDDEN_IMPORT_NAMES:
                        violations.append(f"{path.name}: forbidden import {alias.name}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in FORBIDDEN_MODULE_NAMES:
                        violations.append(f"{path.name}: forbidden import {alias.name}")
            elif isinstance(node, ast.Name) and node.id in FORBIDDEN_IMPORT_NAMES:
                violations.append(f"{path.name}: forbidden name {node.id}")
            elif isinstance(node, ast.Attribute) and node.attr == "build_rolling_context":
                violations.append(f"{path.name}: forbidden rolling context call")

    assert violations == []
