from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Query, status

from backend.db.repositories.alert_repository import alert_repository

router = APIRouter(prefix="", tags=["alerts"])


@router.get("/alerts")
def list_alerts(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    risk_level: str | None = None,
) -> dict[str, Any]:
    items = alert_repository.list_alerts(limit=limit, offset=offset, risk_level=risk_level)
    return {"items": items, "count": len(items)}


@router.get("/alerts/{alert_id}")
def get_alert(alert_id: str) -> dict[str, Any]:
    alert = alert_repository.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert
