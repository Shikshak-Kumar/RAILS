from __future__ import annotations

from typing import Any

from backend.tools.registry import get_tool, list_tools


def run_tool(name: str, **kwargs: Any) -> Any:
    tool = get_tool(name)
    return tool(**kwargs)


__all__ = ['run_tool', 'list_tools']
