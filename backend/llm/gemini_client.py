from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from backend.config import GEMINI_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

# Fallback models in case the primary encounters temporary demand spikes
FALLBACK_MODELS = [
    LLM_MODEL,
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-flash-latest",
    "gemini-pro-latest",
]


class GeminiClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or GEMINI_API_KEY
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 10)

    def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 1500,
    ) -> str | None:
        if not self.is_available():
            return None

        # Try models with fallback
        seen_models: set[str] = set()
        for model in FALLBACK_MODELS:
            clean_model = model.replace("models/", "")
            if clean_model in seen_models:
                continue
            seen_models.add(clean_model)

            endpoint = f"{self.base_url}/models/{clean_model}:generateContent?key={self.api_key}"
            body: dict[str, Any] = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_output_tokens,
                },
            }
            if system_instruction:
                body["systemInstruction"] = {
                    "parts": [{"text": system_instruction}]
                }

            try:
                with httpx.Client(timeout=25.0) as client:
                    resp = client.post(endpoint, json=body)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                return parts[0].get("text", "").strip()
                    elif resp.status_code == 503:
                        logger.warning(f"Gemini model {clean_model} temporary 503 spike, trying fallback...")
                        continue
                    else:
                        logger.warning(f"Gemini API returned HTTP {resp.status_code} for {clean_model}: {resp.text[:120]}")
            except Exception as exc:
                logger.warning(f"Gemini network call failed for {clean_model}: {exc}")
                continue

        return None


gemini_client = GeminiClient()
