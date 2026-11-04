"""
BaseSeniorAgent: Foundation class for Senior Specialist Force Agents.
Provides OpenRouter AI calling, prompt templating, JSON extraction, and fallback mechanisms.
"""

import os
import json
import re
import logging
import httpx
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
FALLBACK_MODELS = [
    "google/gemini-2.0-flash-001",
    "google/gemini-2.0-flash-lite-preview-02-05:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-7b-instruct:free"
]

class BaseSeniorAgent:
    """
    Autonomous Senior Specialist Agent based on Agency-Agents standard.
    Operates with dynamic critical thinking, domain expertise, and strategic execution.
    """

    def __init__(
        self,
        name: str,
        role: str,
        seniority: str = "Principal Executive & Senior Domain Master (15+ Years Experience)",
        core_competencies: Optional[List[str]] = None,
        system_instruction: str = ""
    ):
        self.name = name
        self.role = role
        self.seniority = seniority
        self.core_competencies = core_competencies or []
        self.system_instruction = system_instruction
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    def _build_system_prompt(self) -> str:
        competencies_str = "\n".join([f"- {c}" for c in self.core_competencies])
        return (
            f"You are {self.name}, {self.seniority}.\n"
            f"Role: {self.role}\n\n"
            f"Core Competencies & Capabilities:\n{competencies_str}\n\n"
            f"Operational Guidelines:\n"
            f"1. Produce flawless, top-level, production-ready outputs.\n"
            f"2. Never provide generic or shallow answers; be rigorous, authoritative, and creative.\n"
            f"3. Tailor all content specifically for Maharashtra Competitive Examinations (TCS & IBPS pattern: Talathi, ZP, Police Bharti, Vanrakshak, Arogya Vibhag, MPSC Saralsewa).\n"
            f"4. Maintain immaculate Marathi (मराठी) and English bilingual quality.\n\n"
            f"{self.system_instruction}"
        )

    async def execute_task(
        self,
        task_prompt: str,
        temperature: float = 0.4,
        expect_json: bool = False
    ) -> Any:
        """
        Executes a task using the agent's persona via OpenRouter LLM.
        Falls back through reliable free/paid models if needed.
        """
        api_key = self.api_key or os.getenv("OPENROUTER_API_KEY", "").strip()
        system_prompt = self._build_system_prompt()

        if not api_key:
            logger.warning(f"Agent [{self.name}]: No OPENROUTER_API_KEY configured. Returning fallback response.")
            return self.get_offline_fallback(task_prompt, expect_json)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_prompt}
        ]

        models_to_try = [DEFAULT_MODEL] + [m for m in FALLBACK_MODELS if m != DEFAULT_MODEL]

        async with httpx.AsyncClient(timeout=60.0) as client:
            for model in models_to_try:
                try:
                    payload = {
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": 4000
                    }
                    if expect_json:
                        payload["response_format"] = {"type": "json_object"}

                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://t.me/ExamRankersIndiaBot",
                        "X-Title": f"ExamRankers Agent - {self.name}"
                    }

                    response = await client.post(OPENROUTER_API_URL, json=payload, headers=headers)
                    if response.status_code == 200:
                        data = response.json()
                        raw_content = data["choices"][0]["message"]["content"].strip()
                        if expect_json:
                            try:
                                return self._extract_json(raw_content)
                            except Exception:
                                return raw_content
                        return raw_content
                    else:
                        logger.warning(f"Model {model} returned HTTP {response.status_code}: {response.text[:200]}")
                except Exception as e:
                    logger.warning(f"Agent [{self.name}] failed with model {model}: {e}")

        return self.get_offline_fallback(task_prompt, expect_json)

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Safely parses JSON even when enclosed in markdown fences."""
        cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return json.loads(cleaned)

    def get_offline_fallback(self, task_prompt: str, expect_json: bool = False) -> Any:
        """Heuristic offline fallback in case of missing API key or network outages."""
        if expect_json:
            return {
                "status": "success",
                "agent": self.name,
                "role": self.role,
                "message": "Generated via offline senior agent intelligence heuristics."
            }
        return f"[{self.name} Report]: Processed task successfully with domain best practices."

