from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class StepRecord:
    step_id: str
    name: str
    step_type: str
    status: str
    started_at: str
    completed_at: str | None = None
    duration_ms: float = 0.0
    arguments: dict[str, Any] = field(default_factory=dict)
    result_summary: str = ""
    evidence_id: str | None = None
    error: str | None = None


@dataclass
class ExecutionRecord:
    execution_id: str
    name: str
    status: str
    started_at: str
    input_query: str = ""
    completed_at: str | None = None
    duration_ms: float = 0.0
    steps: list[StepRecord] = field(default_factory=list)
    final_answer: str | None = None
    error: str | None = None


class ExecutionService:
    def __init__(self) -> None:
        self._executions: dict[str, ExecutionRecord] = {}

    def start_execution(self, name: str, input_query: str = "") -> str:
        exec_id = f"exec-{uuid4().hex[:10]}"
        now_str = datetime.now(timezone.utc).isoformat()
        record = ExecutionRecord(
            execution_id=exec_id,
            name=name,
            status="RUNNING",
            started_at=now_str,
            input_query=input_query,
            steps=[],
        )
        self._executions[exec_id] = record
        return exec_id

    def add_step(
        self,
        execution_id: str,
        name: str,
        step_type: str = "tool",
        arguments: dict[str, Any] | None = None,
    ) -> str:
        exec_record = self._executions.get(execution_id)
        step_id = f"step-{uuid4().hex[:8]}"
        step = StepRecord(
            step_id=step_id,
            name=name,
            step_type=step_type,
            status="RUNNING",
            started_at=datetime.now(timezone.utc).isoformat(),
            arguments=self._sanitize_args(arguments or {}),
        )
        if exec_record:
            exec_record.steps.append(step)
        return step_id

    def complete_step(
        self,
        execution_id: str,
        step_id: str,
        *,
        result_summary: str = "",
        evidence_id: str | None = None,
        duration_ms: float = 0.0,
        error: str | None = None,
    ) -> None:
        exec_record = self._executions.get(execution_id)
        if not exec_record:
            return
        for s in exec_record.steps:
            if s.step_id == step_id:
                s.completed_at = datetime.now(timezone.utc).isoformat()
                s.duration_ms = round(duration_ms, 2)
                s.result_summary = result_summary
                s.evidence_id = evidence_id
                s.error = error
                s.status = "FAILED" if error else "COMPLETED"
                break

    def finish_execution(
        self,
        execution_id: str,
        *,
        final_answer: str | None = None,
        status: str = "COMPLETED",
        error: str | None = None,
    ) -> ExecutionRecord | None:
        exec_record = self._executions.get(execution_id)
        if not exec_record:
            return None
        now = datetime.now(timezone.utc)
        exec_record.completed_at = now.isoformat()
        try:
            start_dt = datetime.fromisoformat(exec_record.started_at)
            exec_record.duration_ms = round((now - start_dt).total_seconds() * 1000.0, 2)
        except Exception:
            exec_record.duration_ms = 0.0
        exec_record.status = status
        exec_record.final_answer = final_answer
        exec_record.error = error
        return exec_record

    def list_executions(self, limit: int = 50) -> list[dict[str, Any]]:
        sorted_records = sorted(
            self._executions.values(),
            key=lambda x: x.started_at,
            reverse=True,
        )
        return [asdict(r) for r in sorted_records[:limit]]

    def get_execution(self, execution_id: str) -> dict[str, Any] | None:
        record = self._executions.get(execution_id)
        if not record:
            return None
        return asdict(record)

    def get_steps(self, execution_id: str) -> list[dict[str, Any]]:
        record = self._executions.get(execution_id)
        if not record:
            return []
        return [asdict(s) for s in record.steps]

    @staticmethod
    def _sanitize_args(args: dict[str, Any]) -> dict[str, Any]:
        sanitized = {}
        for k, v in args.items():
            if any(secret in k.lower() for secret in ("password", "secret", "token", "key")):
                sanitized[k] = "******"
            elif isinstance(v, (str, int, float, bool)) or v is None:
                sanitized[k] = v
            else:
                sanitized[k] = str(v)[:80]
        return sanitized


execution_service = ExecutionService()
