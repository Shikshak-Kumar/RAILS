from __future__ import annotations

# ── Path bootstrap — allows running from inside backend/ or from project root ──
import sys, pathlib
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── Router imports (all real implementations) ────────────────────────────────
from backend.api.alerts import router as alerts_router
from backend.api.cases import router as cases_router
from backend.api.copilot import router as copilot_router
from backend.api.executions import router as executions_router
from backend.api.reports import router as reports_router
from backend.api.evidence import router as evidence_router
from backend.api.risk import router as risk_router
from backend.api.transactions import router as transactions_router
from backend.db.repositories.alert_repository import alert_repository
from backend.db.repositories.transaction_repository import transaction_repository
from backend.services.case_service import case_service
from backend.ml.model_loader import MODEL_LOADER

app = FastAPI(title="RAILS Risk Sentinel", version="0.1.0")

# ── CORS — allow the Vite dev server and any future deployed frontend ─────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ─────────────────────────────────────────────────────────────────────────────

# Register routers FIRST so their paths win over any stubs below
app.include_router(transactions_router)
app.include_router(risk_router)
app.include_router(alerts_router)
app.include_router(cases_router)
app.include_router(reports_router)
app.include_router(copilot_router)
app.include_router(evidence_router)
app.include_router(executions_router)


# ── Stand-alone endpoints (no dedicated router file) ─────────────────────────

@app.get("/health", tags=["health"])
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "RAILS Risk Sentinel",
        "models": {
            "fraud_model": MODEL_LOADER.status("fraud_model"),
            "anomaly_model": MODEL_LOADER.status("anomaly_model"),
            "account_risk_model": MODEL_LOADER.status("account_risk_model"),
            "liquidity_model": MODEL_LOADER.status("liquidity_model"),
            "credit_model": MODEL_LOADER.status("credit_model"),
        },
    }


from pydantic import BaseModel

from backend.db.repositories.report_repository import report_repository
from backend.services.simulation_service import simulation_service


class SimulationRequest(BaseModel):
    type: str = 'normal'
    count: int = 20


import time

_OVERVIEW_CACHE: dict[str, Any] = {}
_OVERVIEW_CACHE_TIME: float = 0.0


def invalidate_overview_cache() -> None:
    global _OVERVIEW_CACHE_TIME
    _OVERVIEW_CACHE_TIME = 0.0


@app.get("/overview", tags=["overview"])
def overview() -> dict[str, object]:
    global _OVERVIEW_CACHE, _OVERVIEW_CACHE_TIME
    now = time.time()
    if _OVERVIEW_CACHE and (now - _OVERVIEW_CACHE_TIME) < 10.0:
        return dict(_OVERVIEW_CACHE)

    total_tx = transaction_repository.count_total()

    # Query all write-DB aggregates (alerts, cases, reports) in ONE single query over ONE connection
    alert_counts: dict[str, int] = {}
    case_counts: dict[str, int] = {}
    report_counts: dict[str, int] = {}

    from backend.db.persistence import get_write_connection
    try:
        with get_write_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT 'alert' AS metric, risk_level AS label, count(*)::bigint AS cnt FROM alerts GROUP BY risk_level
                    UNION ALL
                    SELECT 'case' AS metric, status AS label, count(*)::bigint AS cnt FROM cases GROUP BY status
                    UNION ALL
                    SELECT 'report' AS metric, status AS label, count(*)::bigint AS cnt FROM reports GROUP BY status;
                """
                cur.execute(query)
                for metric, label, cnt in cur.fetchall():
                    c = int(cnt)
                    if metric == 'alert':
                        alert_counts[label] = c
                    elif metric == 'case':
                        case_counts[label] = c
                    elif metric == 'report':
                        report_counts[label] = c
    except Exception:
        # Fall back to in-memory counts if DB connection is unavailable
        for a in alert_repository._alerts.values():
            rl = a.get('risk_level') or 'LOW'
            alert_counts[rl] = alert_counts.get(rl, 0) + 1
        for c in case_service.list_cases():
            st = c.status if hasattr(c, 'status') else c.get('status', 'OPEN')
            case_counts[st] = case_counts.get(st, 0) + 1
        for r in report_repository._reports.values():
            rst = r.get('status', 'DRAFT')
            report_counts[rst] = report_counts.get(rst, 0) + 1

    high_alerts = alert_counts.get('HIGH', 0)
    critical_alerts = alert_counts.get('CRITICAL', 0)
    medium_alerts = alert_counts.get('MEDIUM', 0)
    total_alerts = sum(alert_counts.values())

    open_cases = case_counts.get('OPEN', 0) + case_counts.get('UNDER_REVIEW', 0)
    total_cases = sum(case_counts.values())

    total_reports = sum(report_counts.values())
    pending_reports = report_counts.get('DRAFT', 0) + report_counts.get('IN_REVIEW', 0)

    result = {
        "total_transactions": total_tx,
        "transactions_analyzed": total_alerts,
        "high_risk_transactions": high_alerts,
        "critical_alerts": critical_alerts,
        "high_risk_accounts": high_alerts + critical_alerts,
        "open_cases": open_cases,
        "count_cases": total_cases,
        "count_reports": total_reports,
        "pending_reports": pending_reports,
        "liquidity_alerts": 0,
        "credit_alerts": 0,
        "fraud_detected": high_alerts + critical_alerts,
        "total_volume": 128450000.0,
        "avg_risk_score": 0.05,
        "risk_distribution": {
            "critical": critical_alerts,
            "high": high_alerts,
            "medium": medium_alerts,
            "low": max(0, total_tx - (critical_alerts + high_alerts + medium_alerts)),
        },
        "model_status": {
            "fraud_model": MODEL_LOADER.status("fraud_model"),
            "anomaly_model": MODEL_LOADER.status("anomaly_model"),
            "account_risk_model": MODEL_LOADER.status("account_risk_model"),
            "liquidity_model": MODEL_LOADER.status("liquidity_model"),
            "credit_model": MODEL_LOADER.status("credit_model"),
        },
        "backend_status": "ok",
        "data_source_status": "ready",
    }

    _OVERVIEW_CACHE = result
    _OVERVIEW_CACHE_TIME = now
    return result


@app.post("/simulation/start", tags=["simulation"])
@app.post("/simulation", tags=["simulation"])
def simulation_start(req: SimulationRequest = SimulationRequest()) -> dict[str, object]:
    job_id = simulation_service.start_simulation_job(req.type, req.count)
    return {"job_id": job_id, "status": "QUEUED"}


@app.get("/simulation/{job_id}", tags=["simulation"])
def simulation_status(job_id: str) -> dict[str, object]:
    job = simulation_service.get_job(job_id)
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Simulation job not found")
    return job


@app.post("/simulation/transaction", tags=["simulation"])
def simulation_transaction(payload: dict[str, object]) -> dict[str, object]:
    return simulation_service.simulate_transaction(payload)


@app.post("/simulation/liquidity", tags=["simulation"])
def simulation_liquidity(account_id: str) -> dict[str, object]:
    return simulation_service.simulate_liquidity(account_id)

