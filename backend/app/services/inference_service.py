"""InferenceService — LLM extraction with prompt construction, retry, and validation.

Constructs a prompt from parsed lines, calls the LLM API (Anthropic or OpenAI),
validates the JSON response, and returns a list of LLMInferredFact models.

Does NOT write to the database. Called exclusively by IngestionService.

See REQUIREMENTS.md §9.5 for the full contract.
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any

import httpx

from app.config import Settings
from app.exceptions import InferenceApiError, InferenceValidationError
from app.schemas.inferred_fact import VALID_CATEGORIES, LLMInferredFact
from app.services.prefix_parser_service import ParsedLine

logger = logging.getLogger(__name__)

# HTTP status codes that trigger automatic retry.
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# HTTP status codes that must NOT be retried.
_NON_RETRYABLE_STATUS_CODES = frozenset({400, 401})

SYSTEM_PROMPT = """\
You are an expert information extractor for a company intelligence system.

You will receive a series of tagged lines, each in the format `key: text`.
The keys indicate the type of information:
- `p` = person (name, and optionally title after a comma)
- `fn` = functional area / team name
- `rel` = reporting relationship (format: "subordinate > manager")
- `t` = technology / tool
- `proc` = process / methodology
- `cs` = CGKRA current state
- `gw` = CGKRA going well
- `kp` = CGKRA key problem
- `rm` = CGKRA roadmap
- `aop` = CGKRA annual operating plan
- `s` = SWOT strength
- `w` = SWOT weakness
- `o` = SWOT opportunity
- `th` = SWOT threat
- `a` = action item / to-do
- `n` = plain note (extract any identifiable facts of any category)

For each line, extract one or more structured facts. Return ONLY a JSON array.

Rules:
1. Each element MUST have "category" and "value" fields. The "value" field is REQUIRED \
for ALL categories, including relationships.
2. Valid categories: functional-area, person, relationship, technology, process, \
cgkra-cs, cgkra-gw, cgkra-kp, cgkra-rm, cgkra-aop, swot-s, swot-w, swot-o, \
swot-th, action-item, other.
3. For relationship facts, you MUST include ALL THREE fields: "value" (a human-readable \
summary like "Jane Smith reports to Bob Jones"), "subordinate", and "manager" (both \
non-empty strings). Example: {"category": "relationship", "value": "Jane Smith reports \
to Bob Jones", "subordinate": "Jane Smith", "manager": "Bob Jones"}.
4. For `n:` (note) lines, decompose into as many typed facts as the content supports. \
Only use "other" for content that cannot be classified into any specific category.
5. For CGKRA and SWOT lines, preserve the category from the tag exactly — do not \
reclassify based on content.
6. For comma-separated values (e.g., "tech: Kubernetes, Terraform"), produce one fact per item.
7. Return ONLY the JSON array. No prose, no explanation, no markdown code fences.
"""


def _build_user_message(lines: list[ParsedLine]) -> str:
    """Format parsed lines into the LLM user message.

    Each line becomes "canonical_key: text", one per line.
    """
    return "\n".join(f"{line.canonical_key}: {line.text}" for line in lines)


def _strip_code_fence(text: str) -> str:
    """Strip markdown code fences if the LLM wraps its response.

    Handles ```json ... ``` and ``` ... ``` patterns.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        # Remove opening fence (with optional language tag)
        first_newline = stripped.find("\n")
        if first_newline == -1:
            return stripped[3:]
        stripped = stripped[first_newline + 1 :]
        # Remove closing fence
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3].rstrip()
    return stripped


def _validate_response(raw_text: str) -> list[LLMInferredFact]:
    """Validate LLM response and return parsed facts.

    Validation rules (from §9.5):
    1. Parseable as JSON
    2. Top-level is a non-empty array
    3. Every element has a category matching the valid enum
    4. Every element has a non-empty value
    5. Relationship elements have non-empty subordinate and manager

    Raises InferenceValidationError on any failure.
    """
    cleaned = _strip_code_fence(raw_text)

    # 1. Parseable as JSON
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as exc:
        raise InferenceValidationError(
            message=f"LLM returned invalid JSON: {exc}",
            raw_response=raw_text,
        ) from exc

    # 2. Top-level is a non-empty array
    if not isinstance(data, list):
        raise InferenceValidationError(
            message=f"LLM response is not an array (got {type(data).__name__})",
            raw_response=raw_text,
        )
    if len(data) == 0:
        raise InferenceValidationError(
            message="LLM returned an empty array",
            raw_response=raw_text,
        )

    # 3-5. Validate each element via Pydantic
    facts: list[LLMInferredFact] = []
    for i, element in enumerate(data):
        if not isinstance(element, dict):
            raise InferenceValidationError(
                message=f"Element {i} is not an object (got {type(element).__name__})",
                raw_response=raw_text,
            )
        try:
            fact = LLMInferredFact(**element)
        except (ValueError, TypeError) as exc:
            raise InferenceValidationError(
                message=f"Element {i} validation failed: {exc}",
                raw_response=raw_text,
            ) from exc
        facts.append(fact)

    return facts


class InferenceService:
    """LLM-based fact extraction service.

    Constructor accepts settings and an optional HTTP client for DI/mocking.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
    ):
        self._settings = settings
        self._http_client = http_client
        self._max_attempts = settings.llm_max_attempts

    async def extract_facts(
        self, lines: list[ParsedLine]
    ) -> list[LLMInferredFact]:
        """Extract facts from parsed lines via LLM.

        Constructs the prompt, calls the LLM API with retry, validates the
        response, and returns validated LLMInferredFact models.

        Raises:
            InferenceValidationError: LLM response failed validation.
            InferenceApiError: LLM API call failed after retries exhausted.
        """
        if not lines:
            raise InferenceValidationError(
                message="No lines to extract facts from",
                raw_response=None,
            )

        user_message = _build_user_message(lines)
        raw_response = await self._call_llm(user_message)
        return _validate_response(raw_response)

    async def _call_llm(self, user_message: str) -> str:
        """Call the LLM API with retry policy per §9.5.

        Returns the raw text response on success.
        Raises InferenceApiError after retries exhausted.
        """
        provider = self._settings.llm_provider.lower()
        last_error: Exception | None = None

        for attempt in range(self._max_attempts):
            try:
                if provider == "anthropic":
                    return await self._call_anthropic(user_message)
                elif provider == "openai":
                    return await self._call_openai(user_message)
                else:
                    raise InferenceApiError(
                        f"Unknown LLM provider: {provider!r}"
                    )
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                last_error = exc

                if status in _NON_RETRYABLE_STATUS_CODES:
                    raise InferenceApiError(
                        f"LLM API returned non-retryable HTTP {status}"
                    ) from exc

                if status in _RETRYABLE_STATUS_CODES:
                    if attempt < self._max_attempts - 1:
                        delay = self._backoff_delay(attempt, exc.response)
                        logger.warning(
                            "LLM API HTTP %d on attempt %d/%d, retrying in %.1fs",
                            status,
                            attempt + 1,
                            self._max_attempts,
                            delay,
                        )
                        await self._sleep(delay)
                        continue
                    # Final attempt failed
                    raise InferenceApiError(
                        f"LLM API unavailable after {self._max_attempts} attempts: HTTP {status}"
                    ) from exc

                # Unknown error status — don't retry
                raise InferenceApiError(
                    f"LLM API returned unexpected HTTP {status}"
                ) from exc

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_error = exc
                if attempt < self._max_attempts - 1:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "LLM API timeout/connection error on attempt %d/%d, retrying in %.1fs",
                        attempt + 1,
                        self._max_attempts,
                        delay,
                    )
                    await self._sleep(delay)
                    continue
                raise InferenceApiError(
                    f"LLM API unavailable after {self._max_attempts} attempts: {exc}"
                ) from exc

        # Should not reach here, but defensive
        raise InferenceApiError(
            f"LLM API failed after {self._max_attempts} attempts"
        )

    async def _call_anthropic(self, user_message: str) -> str:
        """Call the Anthropic Messages API."""
        client = self._get_client()
        url = self._settings.llm_api_url or "https://api.anthropic.com/v1/messages"
        model = self._settings.llm_model or "claude-sonnet-4-20250514"

        response = await client.post(
            url,
            headers={
                "x-api-key": self._settings.llm_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 4096,
                "system": SYSTEM_PROMPT,
                "messages": [
                    {"role": "user", "content": user_message},
                ],
            },
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        # Anthropic returns content as a list of content blocks
        return data["content"][0]["text"]

    async def _call_openai(self, user_message: str) -> str:
        """Call the OpenAI Chat Completions API."""
        client = self._get_client()
        url = self._settings.llm_api_url or "https://api.openai.com/v1/chat/completions"
        model = self._settings.llm_model or "gpt-4o"

        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {self._settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _get_client(self) -> httpx.AsyncClient:
        """Return the HTTP client, creating a default if none was injected.

        TODO(Phase 8): inject a shared client from the DI layer and close it
        during application shutdown instead of lazily creating one here.
        """
        if self._http_client is None:
            self._http_client = httpx.AsyncClient()
        return self._http_client

    @staticmethod
    def _backoff_delay(
        attempt: int,
        response: httpx.Response | None = None,
    ) -> float:
        """Compute backoff delay with jitter.

        For HTTP 429 with Retry-After header, use that value.
        Otherwise: ~1s for attempt 0, ~2-4s for attempt 1.
        """
        if response is not None:
            retry_after = response.headers.get("retry-after")
            if retry_after is not None:
                try:
                    return float(retry_after)
                except ValueError:
                    pass

        # Exponential backoff: 2^attempt seconds, with jitter ±50%
        base = 2**attempt
        jitter = random.uniform(0.5, 1.5)
        return base * jitter

    @staticmethod
    async def _sleep(seconds: float) -> None:
        """Sleep — extracted for testability (can be mocked to avoid real delays)."""
        import asyncio

        await asyncio.sleep(seconds)
