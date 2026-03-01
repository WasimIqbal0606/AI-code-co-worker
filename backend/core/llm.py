"""
Mistral LLM adapter with dynamic temperature intelligence.
Loads MISTRAL_API_KEY directly from environment variables.
Selects optimal temperature per task type for deterministic vs creative work.
"""

from __future__ import annotations

import asyncio
import enum
import json
import os
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# ── Task-Aware Temperature System ────────────────────────────────────

class TaskType(str, enum.Enum):
    """Task types that determine optimal LLM temperature."""
    SECURITY_SCAN = "security_scan"         # Deterministic: find exact vulnerabilities
    CODE_ANALYSIS = "code_analysis"         # Deterministic: analyze patterns precisely
    TEST_GENERATION = "test_generation"     # Semi-creative: generate valid test code
    REMEDIATION = "remediation"             # Precise: generate production-ready fixes
    ARCHITECTURE = "architecture"           # Creative: propose design improvements
    STRATEGIC_PLANNING = "strategic_planning"  # Analytical: prioritize and plan
    CRITIC_REVIEW = "critic_review"         # Deterministic: evaluate evidence strictly
    PROMPT_ANALYSIS = "prompt_analysis"     # Semi-creative: improve prompts
    ROUTING = "routing"                     # Deterministic: decide which agents
    GENERAL = "general"                     # Default


# Temperature map: lower = more deterministic, higher = more creative
TASK_TEMPERATURE_MAP: dict[TaskType, float] = {
    TaskType.SECURITY_SCAN: 0.1,       # Precise vulnerability detection
    TaskType.CODE_ANALYSIS: 0.1,       # Exact pattern matching
    TaskType.TEST_GENERATION: 0.3,     # Creative but valid test code
    TaskType.REMEDIATION: 0.15,        # Precise fixes, slight flexibility
    TaskType.ARCHITECTURE: 0.4,        # Creative design proposals
    TaskType.STRATEGIC_PLANNING: 0.2,  # Analytical prioritization
    TaskType.CRITIC_REVIEW: 0.1,       # Strict evidence evaluation
    TaskType.PROMPT_ANALYSIS: 0.35,    # Creative prompt improvements
    TaskType.ROUTING: 0.05,            # Near-deterministic routing
    TaskType.GENERAL: 0.2,             # Balanced default
}


def get_temperature(task_type: TaskType) -> float:
    """Get the optimal temperature for a given task type."""
    return TASK_TEMPERATURE_MAP.get(task_type, 0.2)


# ── Abstract Adapter ─────────────────────────────────────────────────

class LLMAdapter(ABC):
    @abstractmethod
    async def generate_json(
        self, system_prompt: str, user_prompt: str,
        schema_json: dict | None = None,
        task_type: TaskType = TaskType.GENERAL,
    ) -> dict:
        ...

    @abstractmethod
    async def generate_text(
        self, system_prompt: str, user_prompt: str,
        task_type: TaskType = TaskType.GENERAL,
    ) -> str:
        ...


# ── Mistral Adapter ─────────────────────────────────────────────────

class MistralAdapter(LLMAdapter):
    """
    Production Mistral adapter with dynamic temperature intelligence.
    Uses client.chat.complete_async() for async chat completions.

    Temperature is selected dynamically per task type:
    - Security/Critic: 0.1 (deterministic — find exact vulnerabilities)
    - Remediation: 0.15 (precise — generate correct fixes)
    - Tests: 0.3 (semi-creative — valid but varied test scenarios)
    - Architecture: 0.4 (creative — propose design improvements)
    - Routing: 0.05 (near-deterministic — reliable agent selection)

    Includes automatic JSON parsing with retry on invalid output.
    Includes automatic retry with exponential backoff for rate limit (429) errors.
    """

    MAX_JSON_RETRIES = 2
    MAX_RATE_LIMIT_RETRIES = 4
    RATE_LIMIT_BASE_DELAY = 5  # seconds

    def __init__(
        self,
        default_temperature: float = 0.2,
        max_tokens: int = 32000,
    ):
        from mistralai import Mistral

        self.api_key = os.getenv("MISTRAL_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "MISTRAL_API_KEY not found in environment variables."
            )

        self.model = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
        self.default_temperature = default_temperature
        self.max_tokens = max_tokens
        self.client = Mistral(api_key=self.api_key)

        logger.info(f"MistralAdapter initialised — model={self.model}")

    def _resolve_temperature(self, task_type: TaskType) -> float:
        """Resolve the optimal temperature for a given task type."""
        temp = get_temperature(task_type)
        logger.debug(f"Temperature for {task_type.value}: {temp}")
        return temp

    # ── JSON generation with auto-retry ──────────────────────────────

    async def generate_json(
        self, system_prompt: str, user_prompt: str,
        schema_json: dict | None = None,
        task_type: TaskType = TaskType.GENERAL,
    ) -> dict:
        """
        Generate a JSON response from Mistral.

        Uses response_format={"type": "json_object"} for structured output.
        Automatically retries up to MAX_JSON_RETRIES times if the response
        is not valid JSON. Raises a clean error on final failure.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_error: Exception | None = None
        last_raw: str = ""

        for attempt in range(1 + self.MAX_JSON_RETRIES):
            for rate_attempt in range(self.MAX_RATE_LIMIT_RETRIES):
                try:
                    resp = await self.client.chat.complete_async(
                        model=self.model,
                        messages=messages,
                        temperature=self._resolve_temperature(task_type),
                        max_tokens=self.max_tokens,
                        response_format={"type": "json_object"},
                    )
                    break  # Success — exit rate limit retry loop
                except Exception as e:
                    err_str = str(e)
                    if "429" in err_str or "rate_limit" in err_str.lower():
                        delay = self.RATE_LIMIT_BASE_DELAY * (2 ** rate_attempt)
                        logger.warning(
                            f"Rate limited (attempt {rate_attempt + 1}/{self.MAX_RATE_LIMIT_RETRIES}), "
                            f"retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        raise RuntimeError(
                            f"Mistral API call failed: {e}"
                        ) from e
            else:
                raise RuntimeError(
                    f"Mistral API rate limit exceeded after {self.MAX_RATE_LIMIT_RETRIES} retries"
                )

            try:
                content = resp.choices[0].message.content or "{}"
                last_raw = content

                # Strip markdown code fences if the model wraps its output
                cleaned = content.strip()
                if cleaned.startswith("```"):
                    first_newline = cleaned.index("\n")
                    cleaned = cleaned[first_newline + 1:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

                return json.loads(cleaned)

            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(
                    f"MistralAdapter JSON parse failed (attempt {attempt + 1}/"
                    f"{1 + self.MAX_JSON_RETRIES}): {e}"
                )
                if attempt < self.MAX_JSON_RETRIES:
                    messages.append({"role": "assistant", "content": last_raw})
                    messages.append({
                        "role": "user",
                        "content": (
                            "Your previous response was not valid JSON. "
                            "Please respond with ONLY a valid JSON object, "
                            "no markdown fences or extra text."
                        ),
                    })

        raise ValueError(
            f"Mistral returned invalid JSON after {1 + self.MAX_JSON_RETRIES} attempts. "
            f"Last raw response: {last_raw[:500]!r}  —  "
            f"Parse error: {last_error}"
        )

    # ── Plain text generation ────────────────────────────────────────

    async def generate_text(
        self, system_prompt: str, user_prompt: str,
        task_type: TaskType = TaskType.GENERAL,
    ) -> str:
        """Generate a plain-text response from Mistral with task-aware temperature."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        for rate_attempt in range(self.MAX_RATE_LIMIT_RETRIES):
            try:
                resp = await self.client.chat.complete_async(
                    model=self.model,
                    messages=messages,
                    temperature=self._resolve_temperature(task_type),
                    max_tokens=self.max_tokens,
                )
                return resp.choices[0].message.content or ""
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate_limit" in err_str.lower():
                    delay = self.RATE_LIMIT_BASE_DELAY * (2 ** rate_attempt)
                    logger.warning(
                        f"Rate limited on text gen (attempt {rate_attempt + 1}/"
                        f"{self.MAX_RATE_LIMIT_RETRIES}), retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(
                        f"Mistral API text generation failed: {e}"
                    ) from e
        raise RuntimeError(
            f"Mistral API rate limit exceeded after {self.MAX_RATE_LIMIT_RETRIES} retries"
        )


# ── Factory ──────────────────────────────────────────────────────────

def get_llm() -> LLMAdapter:
    """Return the Mistral LLM adapter."""
    return MistralAdapter()
