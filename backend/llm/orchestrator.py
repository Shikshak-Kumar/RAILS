from __future__ import annotations

from typing import Any

from backend.config import GEMINI_API_KEY, LLM_MODEL, LLM_PROVIDER
from backend.llm.prompts import INTENT_MAP
from backend.tools.runner import run_tool


class LLMOrchestrator:
    def __init__(self) -> None:
        self.provider: str = LLM_PROVIDER       # e.g. "gemini"
        self.model: str = LLM_MODEL             # e.g. "gemini-2.5-flash"
        self.api_key: str = GEMINI_API_KEY
        self.enabled: bool = bool(self.api_key)

    def detect_intent(self, user_message: str) -> str:
        message = (user_message or '').lower()
        if 'case' in message:
            return 'case'
        if 'account' in message or 'liquidity' in message:
            return 'account'
        if 'report' in message or 'docx' in message:
            return 'report'
        if 'transaction' in message or 'fraud' in message or 'anomaly' in message:
            return 'transaction'
        return 'transaction'

    def execute(self, user_message: str, **kwargs: Any) -> dict[str, Any]:
        intent = self.detect_intent(user_message)
        requested_tools = INTENT_MAP.get(intent, ['get_transaction'])
        result: dict[str, Any] = {
            'intent': intent,
            'provider': self.provider,
            'model': self.model,
            'tool_calls': [],
        }
        for tool_name in requested_tools[:2]:
            try:
                tool_result = run_tool(tool_name, **kwargs)
                result['tool_calls'].append({'tool': tool_name, 'result': tool_result})
            except Exception as exc:  # pragma: no cover
                result['tool_calls'].append({'tool': tool_name, 'error': str(exc)})
        return result


orchestrator = LLMOrchestrator()
