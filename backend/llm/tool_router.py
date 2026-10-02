from __future__ import annotations

from typing import Any

from backend.tools.runner import run_tool


class ToolRouter:
    def __init__(self) -> None:
        self.tools = {}

    def register(self, name: str, func: Any) -> None:
        self.tools[name] = func

    def call(self, tool_name: str, **kwargs: Any) -> Any:
        if tool_name in self.tools:
            return self.tools[tool_name](**kwargs)
        return run_tool(tool_name, **kwargs)


tool_router = ToolRouter()
