from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from app.core.repository import ScreenplayRepository


# Port guard: role extraction depends on narrow abstractions while the current
# facade still injects the existing repository and Gemini callables unchanged.
class LLMClient(Protocol):
    def __call__(self, prompt: str, **kwargs: Any) -> Awaitable[str]:
        ...


# Port guard: sleeper injection lets future role tests avoid real delays without
# changing current production timing behavior.
class Sleeper(Protocol):
    def __call__(self, delay: float) -> Awaitable[None]:
        ...


# Port guard: clock injection makes future phase latency logging deterministic
# while current producer code can keep using time.time until moved.
class Clock(Protocol):
    def __call__(self) -> float:
        ...


# Port guard: prompt renderers stay replaceable as prompt catalog adoption grows,
# but existing string-format templates remain the concrete implementation today.
class PromptRenderer(Protocol):
    def __call__(self, template: str, **kwargs: Any) -> str:
        ...


RoleCallback = Callable[..., Awaitable[Any]]

__all__ = [
    "Clock",
    "LLMClient",
    "PromptRenderer",
    "RoleCallback",
    "ScreenplayRepository",
    "Sleeper",
]

