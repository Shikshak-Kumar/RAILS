from __future__ import annotations

from typing import Any

from backend.services.regulatory_rag_service import regulatory_rag_service
from backend.tools.registry import register_tool


@register_tool("regulatory_search")
def regulatory_search(
    query: str,
    jurisdiction: str | None = None,
    limit: int = 5,
    **kwargs: Any,
) -> dict[str, Any]:
    res = regulatory_rag_service.search(
        query=query,
        jurisdiction=jurisdiction,
        limit=limit,
    )
    return res
