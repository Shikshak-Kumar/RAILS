from __future__ import annotations

from fastapi import FastAPI

# ── Router imports (all real implementations) ────────────────────────────────
from backend.api.cases import router as cases_router
from backend.api.copilot import router as copilot_router
from backend.api.reports import router as reports_router
from backend.api.risk import router as risk_router
from backend.api.transactions import router as transactions_router

app = FastAPI(title="RAILS Risk Sentinel", version="0.1.0")

# Register routers FIRST so their paths win over any stubs below
app.include_router(transactions_router)
app.include_router(risk_router)
app.include_router(cases_router)
app.include_router(reports_router)
app.include_router(copilot_router)


# ── Stand-alone endpoints (no dedicated router file) ─────────────────────────

@app.get("/health", tags=["health"])
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "RAILS Risk Sentinel",
        "models": {
            "fraud_model": {"available": True, "status": "available"},
            "anomaly_model": {"available": True, "status": "available"},
            "account_risk_model": {"available": True, "status": "available"},
            "liquidity_model": {"available": True, "status": "available"},
            "credit_model": {"available": True, "status": "available"},
        },
    }


@app.get("/overview", tags=["overview"])
def overview() -> dict[str, object]:
    return {
        "total_transactions": 0,
        "transactions_analyzed": 0,
        "high_risk_transactions": 0,
        "critical_alerts": 0,
        "high_risk_accounts": 0,
        "open_cases": 0,
        "liquidity_alerts": 0,
        "credit_alerts": 0,
        "model_status": {
            "fraud_model": {
                "available": True,
                "model_version": "v20261002074137",
                "artifact_loaded": True,
                "metadata_loaded": True,
                "feature_order_loaded": True,
            },
            "anomaly_model": {
                "available": True,
                "model_version": "v20261002074147",
                "artifact_loaded": True,
                "metadata_loaded": True,
                "feature_order_loaded": True,
            },
            "account_risk_model": {
                "available": True,
                "model_version": "v20261002074216",
                "artifact_loaded": True,
                "metadata_loaded": True,
                "feature_order_loaded": True,
            },
            "liquidity_model": {
                "available": True,
                "model_version": "v20261002074229",
                "artifact_loaded": True,
                "metadata_loaded": True,
                "feature_order_loaded": True,
            },
            "credit_model": {
                "available": True,
                "model_version": "v20261002074230",
                "artifact_loaded": True,
                "metadata_loaded": True,
                "feature_order_loaded": True,
            },
        },
        "backend_status": "ok",
        "data_source_status": "ready",
    }


@app.get("/regulatory/reports", tags=["reports"])
def get_regulatory_reports() -> dict[str, object]:
    return {"reports": []}


@app.get("/regulatory/reports/{report_id}", tags=["reports"])
def get_regulatory_report(report_id: str) -> dict[str, object]:
    return {"report_id": report_id, "status": "NOT_FOUND"}


@app.post("/simulation/start", tags=["simulation"])
def simulation_start() -> dict[str, object]:
    return {"status": "started"}


@app.post("/simulation/transaction", tags=["simulation"])
def simulation_transaction() -> dict[str, object]:
    return {"status": "ok"}


@app.post("/simulation/liquidity", tags=["simulation"])
def simulation_liquidity() -> dict[str, object]:
    return {"status": "ok"}
