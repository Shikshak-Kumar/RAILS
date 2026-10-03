from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from backend.config import GEMINI_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

FALLBACK_MODELS = [
    LLM_MODEL,
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-pro-latest",
]


class GeminiLLMProvider:

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or GEMINI_API_KEY
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 10)

    def health_check(self) -> dict[str, Any]:
        if not self.is_available():
            return {
                "status": "unconfigured",
                "provider": "gemini",
                "model": LLM_MODEL,
                "available": False,
                "message": "GEMINI_API_KEY is not configured or too short.",
            }

        sample = self.generate("ping", temperature=0.1, max_output_tokens=10)
        healthy = sample is not None
        return {
            "status": "healthy" if healthy else "degraded",
            "provider": "gemini",
            "model": LLM_MODEL,
            "available": healthy,
            "message": "Gemini LLM Provider is operational." if healthy else "Gemini API failed to return response.",
        }

    def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 1500,
    ) -> str | None:
        if not self.is_available():
            return None

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
                    elif resp.status_code in (429, 503):
                        logger.warning(f"Gemini model {clean_model} rate limit / 503 ({resp.status_code}), trying fallback...")
                        continue
                    else:
                        logger.warning(f"Gemini API returned HTTP {resp.status_code} for {clean_model}: {resp.text[:120]}")
            except Exception as exc:
                logger.warning(f"Gemini network call failed for {clean_model}: {exc}")
                continue

        return None

    def generate_structured(
        self,
        prompt: str,
        schema: Any | None = None,
        system_instruction: str | None = None,
        temperature: float = 0.1,
    ) -> dict[str, Any] | None:
        instructions = [system_instruction or "You are an intelligent structured data generator."]
        instructions.append("Respond ONLY with valid, raw JSON (no conversational text outside JSON, no markdown backticks).")
        if schema:
            if hasattr(schema, "model_json_schema"):
                instructions.append(f"Target JSON Schema: {json.dumps(schema.model_json_schema())}")
            elif isinstance(schema, dict):
                instructions.append(f"Target JSON Structure: {json.dumps(schema)}")

        full_instruction = "\n\n".join(instructions)
        raw_text = self.generate(
            prompt=prompt,
            system_instruction=full_instruction,
            temperature=temperature,
            max_output_tokens=2000,
        )
        if not raw_text:
            return None

        clean = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.IGNORECASE)
        clean = re.sub(r"\s*```$", "", clean)

        try:
            parsed = json.loads(clean)
            if isinstance(parsed, dict):
                return parsed
        except Exception as err:
            logger.warning(f"Failed to parse structured JSON from Gemini: {err}\nRaw text: {raw_text[:200]}")

        return None


gemini_provider = GeminiLLMProvider()
GeminiClient = GeminiLLMProvider
gemini_client = gemini_provider

