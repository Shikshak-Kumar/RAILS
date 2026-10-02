from __future__ import annotations

from typing import Any

from backend.db.repositories.alert_repository import alert_repository
from backend.tools.registry import register_tool


@register_tool('list_alerts')
def list_alerts(risk_level: str | None = None, limit: int = 10, offset: int = 0, **kwargs: Any) -> dict[str, Any]:
    alerts = alert_repository.list_alerts(risk_level=risk_level, limit=limit, offset=offset)
    return {'count': len(alerts), 'items': alerts}


@register_tool('get_alert')
def get_alert(alert_id: str, **kwargs: Any) -> dict[str, Any]:
    res = alert_repository.get_alert(alert_id)
    return res or {'alert_id': alert_id, 'found': False}
