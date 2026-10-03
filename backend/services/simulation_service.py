from __future__ import annotations

import json
import random
import threading
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from backend.db.persistence import get_write_connection
from backend.schemas.transaction import TransactionInput
from backend.services.risk_service import risk_service


class SimulationService:
    def __init__(self) -> None:
        self.risk_service = risk_service
        self._jobs: dict[str, dict[str, Any]] = {}

    def start_simulation_job(self, scenario_type: str, count: int = 20) -> str:
        job_id = f"simjob-{uuid4().hex[:10]}"
        count = max(1, min(count, 100))
        now_str = datetime.now(timezone.utc).isoformat()
        
        job_data = {
            "job_id": job_id,
            "scenario": scenario_type,
            "status": "QUEUED",
            "completed": 0,
            "total": count,
            "progress": 0,
            "current_step": "queued",
            "current_transaction_id": None,
            "alerts_created": 0,
            "results": [],
            "summary": {},
            "error": None,
            "created_at": now_str,
            "started_at": None,
            "completed_at": None,
        }
        self._jobs[job_id] = job_data

        self._db_insert_job(job_data)

        thread = threading.Thread(
            target=self._execute_job,
            args=(job_id, scenario_type, count),
            daemon=True,
        )
        thread.start()
        return job_id

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        if job_id in self._jobs:
            return dict(self._jobs[job_id])

        db_job = self._db_get_job(job_id)
        if db_job:
            self._jobs[job_id] = db_job
            return db_job

        return None

    def _execute_job(self, job_id: str, scenario_type: str, count: int) -> None:
        now = datetime.now(timezone.utc)
        evaluated_transactions: list[dict[str, Any]] = []
        alerts_created = 0

        self._jobs[job_id]["status"] = "RUNNING"
        self._jobs[job_id]["started_at"] = now.isoformat()
        self._jobs[job_id]["current_step"] = "generating_scenarios"

        primary_sender = f"ACC_SIM_S_{uuid4().hex[:6]}"
        primary_receiver = f"ACC_SIM_R_{uuid4().hex[:6]}"

        for i in range(count):
            tx_id = f"sim-{uuid4().hex[:8]}"
            tx_time = now - timedelta(seconds=(count - i) * 30)

            if scenario_type == 'normal':
                sender = f"ACC_NORM_{random.randint(100, 999)}"
                receiver = f"ACC_NORM_{random.randint(100, 999)}"
                amount = round(random.uniform(25.0, 450.0), 2)
                tx_type = random.choice(['ACH', 'DEBIT', 'TRANSFER'])
                sender_history = [
                    {'transaction_id': f"dep-1", 'sender_id': 'EMPLOYER_PAYROLL', 'receiver_id': sender, 'amount': 3500.0, 'timestamp': tx_time - timedelta(days=5)},
                    {'transaction_id': f"hist-1", 'sender_id': sender, 'receiver_id': 'UTILITY_CORP', 'amount': 120.0, 'timestamp': tx_time - timedelta(days=4)},
                    {'transaction_id': f"hist-2", 'sender_id': sender, 'receiver_id': receiver, 'amount': round(random.uniform(30.0, 100.0), 2), 'timestamp': tx_time - timedelta(days=2)},
                ]
                pair_history = [
                    {'transaction_id': f"pair-1", 'sender_id': sender, 'receiver_id': receiver, 'amount': 85.0, 'timestamp': tx_time - timedelta(days=2)},
                ]

            elif scenario_type == 'high_velocity':
                sender = primary_sender
                receiver = f"ACC_RX_{i}"
                amount = round(random.uniform(800.0, 2500.0), 2)
                tx_type = 'WIRE'
                sender_history = [
                    {'transaction_id': f"burst-{j}", 'sender_id': sender, 'receiver_id': f"rx-{j}", 'amount': 1200.0, 'timestamp': tx_time - timedelta(minutes=j + 1)}
                    for j in range(6)
                ]

            elif scenario_type == 'fan_in':
                sender = f"ACC_MULE_{i}"
                receiver = primary_receiver
                amount = round(random.uniform(4000.0, 9500.0), 2)
                tx_type = 'TRANSFER'
                sender_history = []

            elif scenario_type == 'fan_out':
                sender = primary_sender
                receiver = f"ACC_DEST_{i}"
                amount = round(random.uniform(3000.0, 8000.0), 2)
                tx_type = 'WIRE'
                sender_history = [
                    {'transaction_id': f"out-{j}", 'sender_id': sender, 'receiver_id': f"rx-{j}", 'amount': 5000.0, 'timestamp': tx_time - timedelta(minutes=(j + 1) * 2)}
                    for j in range(5)
                ]

            elif scenario_type == 'rapid_fund_movement':
                sender = primary_sender
                receiver = primary_receiver
                amount = round(random.uniform(15000.0, 45000.0), 2)
                tx_type = 'WIRE'
                sender_history = [
                    {'transaction_id': "in-flow", 'sender_id': "acc-source", 'receiver_id': sender, 'amount': amount + 500.0, 'timestamp': tx_time - timedelta(minutes=5)}
                ]

            elif scenario_type == 'unusual_amount':
                sender = primary_sender
                receiver = primary_receiver
                amount = round(random.uniform(85000.0, 250000.0), 2)
                tx_type = 'WIRE'
                sender_history = [
                    {'transaction_id': f"small-{j}", 'sender_id': sender, 'receiver_id': f"rx-{j}", 'amount': round(random.uniform(100.0, 500.0), 2), 'timestamp': tx_time - timedelta(days=j + 1)}
                    for j in range(8)
                ]

            elif scenario_type == 'liquidity_stress':
                sender = primary_sender
                receiver = primary_receiver
                amount = round(random.uniform(50000.0, 150000.0), 2)
                tx_type = 'WIRE'
                sender_history = [
                    {'transaction_id': f"liq-{j}", 'sender_id': sender, 'receiver_id': f"rx-{j}", 'amount': 40000.0, 'timestamp': tx_time - timedelta(hours=j + 1)}
                    for j in range(5)
                ]

            else:
                is_risky = (i % 3 == 0)
                sender = primary_sender if is_risky else f"ACC_NORM_{i}"
                receiver = f"ACC_DEST_{i}"
                amount = round(random.uniform(45000.0, 95000.0) if is_risky else random.uniform(50.0, 400.0), 2)
                tx_type = 'WIRE' if is_risky else 'TRANSFER'
                sender_history = [
                    {'transaction_id': f"hist-{j}", 'sender_id': sender, 'receiver_id': f"rx-{j}", 'amount': 500.0, 'timestamp': tx_time - timedelta(hours=j + 1)}
                    for j in range(3)
                ] if is_risky else []

            tx_input = TransactionInput(
                transaction_id=tx_id,
                sender_id=sender,
                receiver_id=receiver,
                amount=amount,
                timestamp=tx_time,
                transaction_type=tx_type,
                currency="USD",
            )

            self._jobs[job_id]["current_step"] = f"risk_analysis_{tx_id}"
            self._jobs[job_id]["current_transaction_id"] = tx_id

            assessment = self.risk_service.analyze_transaction(
                tx_input,
                sender_history=sender_history,
                receiver_history=[],
                pair_history=[],
            )

            if assessment.risk_level in ('HIGH', 'CRITICAL'):
                alerts_created += 1

            evaluated_transactions.append({
                'id': tx_id,
                'transaction_id': tx_id,
                'sender_id': sender,
                'receiver_id': receiver,
                'amount': amount,
                'currency': "USD",
                'timestamp': tx_time.isoformat(),
                'transaction_type': tx_type,
                'from_bank': 'SimBank National',
                'to_bank': 'Global Reserve',
                'is_laundering': assessment.risk_level in ('HIGH', 'CRITICAL'),
                'risk_level': assessment.risk_level,
                'risk_score': assessment.risk_score,
                'fraud_probability': assessment.fraud_probability,
                'anomaly_score': assessment.anomaly_score,
                'account_risk_score': assessment.account_risk_score,
                'overall_score': assessment.overall_score or assessment.risk_score,
                'signals': assessment.signals,
                'risk_drivers': assessment.risk_drivers,
                'rule_results': assessment.rule_results,
                'explanation': assessment.explanation,
                'evidence_ids': assessment.evidence_ids,
            })

            self._jobs[job_id]["completed"] = i + 1
            self._jobs[job_id]["progress"] = int(((i + 1) / count) * 100)
            self._jobs[job_id]["alerts_created"] = alerts_created
            self._jobs[job_id]["results"] = list(evaluated_transactions)

        high_risk_count = sum(1 for t in evaluated_transactions if t['risk_level'] in ('HIGH', 'CRITICAL'))
        medium_risk_count = sum(1 for t in evaluated_transactions if t['risk_level'] == 'MEDIUM')
        low_risk_count = sum(1 for t in evaluated_transactions if t['risk_level'] == 'LOW')
        avg_score = sum(t['risk_score'] for t in evaluated_transactions) / max(1, len(evaluated_transactions))

        summary = {
            'total_evaluated': count,
            'high_risk_count': high_risk_count,
            'medium_risk_count': medium_risk_count,
            'low_risk_count': low_risk_count,
            'alerts_created': alerts_created,
            'average_risk_score': round(avg_score, 3),
            'scenario': scenario_type,
            'timestamp': now.isoformat(),
        }

        self._jobs[job_id]["summary"] = summary
        self._jobs[job_id]["status"] = "COMPLETED"
        self._jobs[job_id]["current_step"] = "finished"
        self._jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()

        self._db_update_job(self._jobs[job_id])


    def _db_insert_job(self, job: dict[str, Any]) -> None:
        try:
            with get_write_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO simulation_jobs (
                            job_id, scenario, status, total, completed, progress,
                            current_step, current_transaction_id, alerts_created,
                            results, summary, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, CURRENT_TIMESTAMP)
                        ON CONFLICT (job_id) DO NOTHING;
                        """,
                        (
                            job["job_id"],
                            job["scenario"],
                            job["status"],
                            job["total"],
                            job["completed"],
                            job["progress"],
                            job["current_step"],
                            job["current_transaction_id"],
                            job["alerts_created"],
                            json.dumps(job["results"]),
                            json.dumps(job["summary"]),
                        ),
                    )
        except Exception:
            pass

    def _db_update_job(self, job: dict[str, Any]) -> None:
        try:
            with get_write_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE simulation_jobs SET
                            status = %s,
                            completed = %s,
                            progress = %s,
                            current_step = %s,
                            current_transaction_id = %s,
                            alerts_created = %s,
                            results = %s::jsonb,
                            summary = %s::jsonb,
                            completed_at = CURRENT_TIMESTAMP
                        WHERE job_id = %s;
                        """,
                        (
                            job["status"],
                            job["completed"],
                            job["progress"],
                            job["current_step"],
                            job["current_transaction_id"],
                            job["alerts_created"],
                            json.dumps(job["results"]),
                            json.dumps(job["summary"]),
                            job["job_id"],
                        ),
                    )
        except Exception:
            pass

    def _db_get_job(self, job_id: str) -> dict[str, Any] | None:
        try:
            with get_write_connection() as conn:
                from psycopg.rows import dict_row
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT * FROM simulation_jobs WHERE job_id = %s", (job_id,))
                    row = cur.fetchone()
                    if row:
                        res = dict(row)
                        if isinstance(res.get("results"), str):
                            res["results"] = json.loads(res["results"])
                        if isinstance(res.get("summary"), str):
                            res["summary"] = json.loads(res["summary"])
                        for ts in ("created_at", "started_at", "completed_at"):
                            if isinstance(res.get(ts), datetime):
                                res[ts] = res[ts].isoformat()
                        return res
        except Exception:
            pass
        return None

    def run_simulation(self, scenario_type: str, count: int = 20) -> dict[str, Any]:
        job_id = self.start_simulation_job(scenario_type, count)
        job = self.get_job(job_id)
        return {
            "job_id": job_id,
            "status": job["status"] if job else "QUEUED",
        }

    def simulate_transaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        tx_input = TransactionInput(**payload)
        assessment = self.risk_service.analyze_transaction(tx_input)
        return assessment.model_dump()

    def simulate_liquidity(self, account_id: str) -> dict[str, Any]:
        return {
            "account_id": account_id,
            "stress_index": 0.42,
            "liquidity_status": "NORMAL",
            "volatility_multiplier": 1.25,
            "tested_at": datetime.now(timezone.utc).isoformat(),
        }


simulation_service = SimulationService()
