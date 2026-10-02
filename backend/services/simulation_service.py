from __future__ import annotations

from typing import Any

from backend.services.risk_service import risk_service


class SimulationService:
    def __init__(self) -> None:
        self.risk_service = risk_service

    def simulate_transaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        analysis = self.risk_service.analyze_transaction(payload)
        return {'status': 'ok', 'result': analysis.model_dump(mode='json')}

    def simulate_liquidity(self, account_id: str) -> dict[str, Any]:
        result = self.risk_service.account_risk(account_id)
        return {'status': 'ok', 'account_id': account_id, 'result': result}


simulation_service = SimulationService()
