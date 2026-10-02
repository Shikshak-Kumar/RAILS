from __future__ import annotations

from typing import Any, Callable

TOOL_REGISTRY: dict[str, Callable[..., Any]] = {}


def register_tool(name: str):
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        TOOL_REGISTRY[name] = func
        return func
    return decorator


def list_tools() -> list[str]:
    return sorted(TOOL_REGISTRY)


def get_tool(name: str) -> Callable[..., Any]:
    if name not in TOOL_REGISTRY:
        raise KeyError(f'Unknown tool: {name}')
    return TOOL_REGISTRY[name]
