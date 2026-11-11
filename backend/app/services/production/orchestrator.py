from collections.abc import Awaitable, Callable
from typing import Any

from app.services.production.role_contracts import RoleContext, RoleResult, RoleSpec
from app.services.production.support.sse import sse_event


RoleHandler = Callable[[RoleContext], Awaitable[RoleResult]]


# Orchestrator scaffold guard: the runner is introduced without wiring producer
# call sites, so current generation behavior remains owned by ScriptProducer.
class RoleGraphRunner:
    def __init__(self, role_specs: tuple[RoleSpec, ...], handlers: dict[str, RoleHandler]):
        self.role_specs = role_specs
        self.handlers = handlers

    # Runner guard: execution is deliberately minimal and data-driven; future role
    # extraction can add retries/logging without changing the public role contract.
    async def run(self, context: RoleContext) -> list[RoleResult]:
        results: list[RoleResult] = []
        for spec in self.enabled_specs(context.settings):
            handler = self.handlers[spec.role_name]
            results.append(await handler(context))
        return results

    # Runner guard: optional roles are enabled by context flags, replacing future
    # scattered if/else checks while keeping today's producer untouched.
    def enabled_specs(self, settings: dict[str, Any]) -> tuple[RoleSpec, ...]:
        enabled: list[RoleSpec] = []
        for spec in self.role_specs:
            if spec.optional and spec.enabled_by and not settings.get(spec.enabled_by):
                continue
            enabled.append(spec)
        return tuple(enabled)


# SSE adapter guard: role result streaming starts from existing SSE framing so
# frontend parsing stays stable when role graph output is adopted later.
def role_result_event(result: RoleResult) -> str:
    return sse_event({
        "status": "role_result",
        "role": result.role_name,
        "schema_version": result.schema_version,
        "artifacts": sorted(result.artifacts.keys()),
        "warnings": result.warnings,
        "cache_hit": result.cache_hit,
    })


__all__ = [
    "RoleGraphRunner",
    "RoleHandler",
    "role_result_event",
]

