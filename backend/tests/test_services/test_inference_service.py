"""Tests for InferenceService — prompt construction, LLM call, retry, validation.

All tests mock the HTTP client — no real LLM API calls.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.config import Settings
from app.exceptions import InferenceApiError, InferenceValidationError
from app.schemas.inferred_fact import LLMInferredFact
from app.services.inference_service import (
    RAW_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    InferenceService,
    _build_raw_system_prompt,
    _build_user_message,
    _strip_code_fence,
    _validate_response,
)
from app.services.prefix_parser_service import ParsedLine


# ── Helpers ──────────────────────────────────────────────────────


def _settings(**overrides) -> Settings:
    """Create a Settings instance with LLM defaults for tests."""
    defaults = {
        "database_url": "unused",
        "llm_provider": "anthropic",
        "llm_api_key": "test-key",
        "llm_api_url": "https://test-llm.example.com/v1/messages",
        "llm_model": "test-model",
        "llm_max_attempts": 3,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _mock_client_with_response(
    json_body: dict | list | str,
    status_code: int = 200,
    headers: dict | None = None,
) -> httpx.AsyncClient:
    """Create a mock httpx.AsyncClient that returns a fixed response."""
    mock = AsyncMock(spec=httpx.AsyncClient)

    response = httpx.Response(
        status_code=status_code,
        json=json_body if not isinstance(json_body, str) else None,
        text=json_body if isinstance(json_body, str) else None,
        headers=headers or {},
        request=httpx.Request("POST", "https://test-llm.example.com/v1/messages"),
    )

    mock.post = AsyncMock(return_value=response)
    return mock


def _anthropic_response(content_text: str) -> dict:
    """Build an Anthropic-shaped JSON response body."""
    return {
        "content": [{"type": "text", "text": content_text}],
        "model": "test-model",
        "role": "assistant",
    }


def _openai_response(content_text: str) -> dict:
    """Build an OpenAI-shaped JSON response body."""
    return {
        "choices": [
            {"message": {"role": "assistant", "content": content_text}, "index": 0}
        ],
        "model": "test-model",
    }


def _valid_fact_json(facts: list[dict] | None = None) -> str:
    """Return a valid JSON string of LLM facts."""
    if facts is None:
        facts = [{"category": "person", "value": "Jane Doe"}]
    return json.dumps(facts)


def _sample_lines() -> list[ParsedLine]:
    """Return a few sample ParsedLine objects for tests."""
    return [
        ParsedLine(canonical_key="p", text="Jane Doe, CTO"),
        ParsedLine(canonical_key="fn", text="Engineering"),
    ]


# ── Unit tests: _build_user_message ─────────────────────────────


class TestBuildUserMessage:
    def test_formats_lines(self):
        lines = [
            ParsedLine(canonical_key="p", text="Alice"),
            ParsedLine(canonical_key="fn", text="Sales"),
            ParsedLine(canonical_key="t", text="Kubernetes"),
        ]
        result = _build_user_message(lines)
        assert result == "p: Alice\nfn: Sales\nt: Kubernetes"

    def test_single_line(self):
        lines = [ParsedLine(canonical_key="n", text="some note")]
        result = _build_user_message(lines)
        assert result == "n: some note"

    def test_preserves_text_exactly(self):
        lines = [
            ParsedLine(canonical_key="rel", text="Bob > Alice")
        ]
        result = _build_user_message(lines)
        assert result == "rel: Bob > Alice"


# ── Unit tests: _strip_code_fence ───────────────────────────────


class TestStripCodeFence:
    def test_no_fence(self):
        text = '[{"category": "person", "value": "Jane"}]'
        assert _strip_code_fence(text) == text

    def test_json_fence(self):
        text = '```json\n[{"category": "person", "value": "Jane"}]\n```'
        assert _strip_code_fence(text) == '[{"category": "person", "value": "Jane"}]'

    def test_plain_fence(self):
        text = '```\n[{"category": "person", "value": "Jane"}]\n```'
        assert _strip_code_fence(text) == '[{"category": "person", "value": "Jane"}]'

    def test_fence_with_extra_whitespace(self):
        text = '  ```json\n[{"category": "person", "value": "Jane"}]\n```  '
        assert _strip_code_fence(text) == '[{"category": "person", "value": "Jane"}]'


# ── Unit tests: _validate_response ──────────────────────────────


class TestValidateResponse:
    def test_valid_single_fact(self):
        raw = _valid_fact_json([{"category": "person", "value": "Alice"}])
        facts = _validate_response(raw)
        assert len(facts) == 1
        assert facts[0].category == "person"
        assert facts[0].value == "Alice"

    def test_valid_multiple_facts(self):
        raw = _valid_fact_json([
            {"category": "person", "value": "Alice"},
            {"category": "technology", "value": "Kubernetes"},
            {"category": "functional-area", "value": "Engineering"},
        ])
        facts = _validate_response(raw)
        assert len(facts) == 3
        assert {f.category for f in facts} == {
            "person",
            "technology",
            "functional-area",
        }

    def test_valid_relationship(self):
        raw = _valid_fact_json([
            {
                "category": "relationship",
                "value": "reports-to",
                "subordinate": "Bob",
                "manager": "Alice",
            }
        ])
        facts = _validate_response(raw)
        assert len(facts) == 1
        assert facts[0].subordinate == "Bob"
        assert facts[0].manager == "Alice"

    def test_malformed_json(self):
        with pytest.raises(InferenceValidationError, match="invalid JSON"):
            _validate_response("not json at all")

    def test_empty_array(self):
        with pytest.raises(InferenceValidationError, match="empty array"):
            _validate_response("[]")

    def test_not_array(self):
        with pytest.raises(InferenceValidationError, match="not an array"):
            _validate_response('{"category": "person", "value": "Alice"}')

    def test_element_not_object(self):
        with pytest.raises(InferenceValidationError, match="not an object"):
            _validate_response('["just a string"]')

    def test_missing_category(self):
        with pytest.raises(InferenceValidationError, match="validation failed"):
            _validate_response('[{"value": "Alice"}]')

    def test_missing_value(self):
        with pytest.raises(InferenceValidationError, match="validation failed"):
            _validate_response('[{"category": "person"}]')

    def test_empty_value(self):
        with pytest.raises(InferenceValidationError, match="validation failed"):
            _validate_response('[{"category": "person", "value": "  "}]')

    def test_unknown_category(self):
        with pytest.raises(InferenceValidationError, match="validation failed"):
            _validate_response('[{"category": "bogus", "value": "whatever"}]')

    def test_relationship_missing_subordinate(self):
        with pytest.raises(InferenceValidationError, match="validation failed"):
            _validate_response(
                '[{"category": "relationship", "value": "reports-to", "manager": "Alice"}]'
            )

    def test_relationship_missing_manager(self):
        with pytest.raises(InferenceValidationError, match="validation failed"):
            _validate_response(
                '[{"category": "relationship", "value": "reports-to", "subordinate": "Bob"}]'
            )

    def test_relationship_empty_subordinate(self):
        with pytest.raises(InferenceValidationError, match="validation failed"):
            _validate_response(
                '[{"category": "relationship", "value": "reports-to", '
                '"subordinate": "  ", "manager": "Alice"}]'
            )

    def test_relationship_empty_manager(self):
        with pytest.raises(InferenceValidationError, match="validation failed"):
            _validate_response(
                '[{"category": "relationship", "value": "reports-to", '
                '"subordinate": "Bob", "manager": "  "}]'
            )

    def test_strips_code_fence_before_parsing(self):
        raw = '```json\n[{"category": "person", "value": "Alice"}]\n```'
        facts = _validate_response(raw)
        assert len(facts) == 1
        assert facts[0].value == "Alice"

    def test_preserves_raw_response_on_error(self):
        raw = "broken json {"
        with pytest.raises(InferenceValidationError) as exc_info:
            _validate_response(raw)
        assert exc_info.value.raw_response == raw

    def test_all_valid_categories(self):
        """Every valid category should be accepted."""
        from app.schemas.inferred_fact import VALID_CATEGORIES

        facts_data = []
        for cat in sorted(VALID_CATEGORIES):
            fact = {"category": cat, "value": f"test-{cat}"}
            if cat == "relationship":
                fact["subordinate"] = "Sub"
                fact["manager"] = "Mgr"
            facts_data.append(fact)

        facts = _validate_response(json.dumps(facts_data))
        assert len(facts) == len(VALID_CATEGORIES)


# ── Integration tests: InferenceService.extract_facts ────────────


class TestExtractFactsAnthropicProvider:
    """Tests using the Anthropic provider."""

    @pytest.mark.asyncio
    async def test_valid_response_returns_facts(self):
        facts_json = _valid_fact_json([
            {"category": "person", "value": "Jane Doe"},
            {"category": "technology", "value": "Python"},
        ])
        client = _mock_client_with_response(_anthropic_response(facts_json))
        svc = InferenceService(settings=_settings(), http_client=client)

        result = await svc.extract_facts(_sample_lines())

        assert len(result) == 2
        assert all(isinstance(f, LLMInferredFact) for f in result)
        assert result[0].category == "person"
        assert result[1].value == "Python"

    @pytest.mark.asyncio
    async def test_sends_correct_headers(self):
        facts_json = _valid_fact_json()
        client = _mock_client_with_response(_anthropic_response(facts_json))
        svc = InferenceService(settings=_settings(), http_client=client)

        await svc.extract_facts(_sample_lines())

        call_kwargs = client.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["x-api-key"] == "test-key"
        assert headers["anthropic-version"] == "2023-06-01"

    @pytest.mark.asyncio
    async def test_sends_correct_payload(self):
        facts_json = _valid_fact_json()
        client = _mock_client_with_response(_anthropic_response(facts_json))
        svc = InferenceService(
            settings=_settings(llm_model="test-model"), http_client=client
        )

        await svc.extract_facts(_sample_lines())

        call_kwargs = client.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["model"] == "test-model"
        assert body["system"] == SYSTEM_PROMPT
        assert len(body["messages"]) == 1
        assert body["messages"][0]["role"] == "user"
        # Verify user message format
        assert "p: Jane Doe, CTO" in body["messages"][0]["content"]
        assert "fn: Engineering" in body["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_uses_custom_api_url(self):
        facts_json = _valid_fact_json()
        client = _mock_client_with_response(_anthropic_response(facts_json))
        url = "https://custom.example.com/v1/messages"
        svc = InferenceService(
            settings=_settings(llm_api_url=url), http_client=client
        )

        await svc.extract_facts(_sample_lines())

        call_args = client.post.call_args
        assert call_args[0][0] == url

    @pytest.mark.asyncio
    async def test_uses_default_anthropic_url_when_empty(self):
        facts_json = _valid_fact_json()
        client = _mock_client_with_response(_anthropic_response(facts_json))
        svc = InferenceService(
            settings=_settings(llm_api_url=""), http_client=client
        )

        await svc.extract_facts(_sample_lines())

        call_args = client.post.call_args
        assert call_args[0][0] == "https://api.anthropic.com/v1/messages"


class TestExtractFactsOpenAIProvider:
    """Tests using the OpenAI provider."""

    @pytest.mark.asyncio
    async def test_valid_response_returns_facts(self):
        facts_json = _valid_fact_json([
            {"category": "functional-area", "value": "Marketing"},
        ])
        client = _mock_client_with_response(_openai_response(facts_json))
        svc = InferenceService(
            settings=_settings(llm_provider="openai"), http_client=client
        )

        result = await svc.extract_facts(_sample_lines())

        assert len(result) == 1
        assert result[0].category == "functional-area"

    @pytest.mark.asyncio
    async def test_sends_bearer_auth(self):
        facts_json = _valid_fact_json()
        client = _mock_client_with_response(_openai_response(facts_json))
        svc = InferenceService(
            settings=_settings(llm_provider="openai"), http_client=client
        )

        await svc.extract_facts(_sample_lines())

        call_kwargs = client.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["Authorization"] == "Bearer test-key"

    @pytest.mark.asyncio
    async def test_sends_system_message(self):
        facts_json = _valid_fact_json()
        client = _mock_client_with_response(_openai_response(facts_json))
        svc = InferenceService(
            settings=_settings(llm_provider="openai"), http_client=client
        )

        await svc.extract_facts(_sample_lines())

        call_kwargs = client.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][0]["content"] == SYSTEM_PROMPT
        assert body["messages"][1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_uses_default_openai_url_when_empty(self):
        facts_json = _valid_fact_json()
        client = _mock_client_with_response(_openai_response(facts_json))
        svc = InferenceService(
            settings=_settings(llm_provider="openai", llm_api_url=""),
            http_client=client,
        )

        await svc.extract_facts(_sample_lines())

        call_args = client.post.call_args
        assert call_args[0][0] == "https://api.openai.com/v1/chat/completions"


class TestExtractFactsValidationErrors:
    """Tests for validation errors during extract_facts."""

    @pytest.mark.asyncio
    async def test_empty_lines_raises(self):
        svc = InferenceService(settings=_settings())
        with pytest.raises(InferenceValidationError, match="No lines"):
            await svc.extract_facts([])

    @pytest.mark.asyncio
    async def test_malformed_json_from_llm(self):
        client = _mock_client_with_response(
            _anthropic_response("not valid json {{{")
        )
        svc = InferenceService(settings=_settings(), http_client=client)

        with pytest.raises(InferenceValidationError, match="invalid JSON"):
            await svc.extract_facts(_sample_lines())

    @pytest.mark.asyncio
    async def test_empty_array_from_llm(self):
        client = _mock_client_with_response(_anthropic_response("[]"))
        svc = InferenceService(settings=_settings(), http_client=client)

        with pytest.raises(InferenceValidationError, match="empty array"):
            await svc.extract_facts(_sample_lines())

    @pytest.mark.asyncio
    async def test_unknown_category_from_llm(self):
        bad_json = json.dumps([{"category": "unknown_cat", "value": "test"}])
        client = _mock_client_with_response(_anthropic_response(bad_json))
        svc = InferenceService(settings=_settings(), http_client=client)

        with pytest.raises(InferenceValidationError, match="validation failed"):
            await svc.extract_facts(_sample_lines())

    @pytest.mark.asyncio
    async def test_code_fence_stripped_from_llm(self):
        """LLM wraps valid JSON in markdown code fences — should still work."""
        facts_json = _valid_fact_json([{"category": "person", "value": "Bob"}])
        wrapped = f"```json\n{facts_json}\n```"
        client = _mock_client_with_response(_anthropic_response(wrapped))
        svc = InferenceService(settings=_settings(), http_client=client)

        result = await svc.extract_facts(_sample_lines())
        assert len(result) == 1
        assert result[0].value == "Bob"


class TestExtractFactsUnknownProvider:
    """Test unknown LLM provider."""

    @pytest.mark.asyncio
    async def test_unknown_provider_raises(self):
        svc = InferenceService(
            settings=_settings(llm_provider="gemini"), http_client=AsyncMock()
        )
        with pytest.raises(InferenceApiError, match="Unknown LLM provider"):
            await svc.extract_facts(_sample_lines())


# ── Retry behaviour ─────────────────────────────────────────────


class TestRetryBehaviour:
    """Tests for the retry policy per §9.5."""

    @pytest.mark.asyncio
    async def test_http_429_retries_then_succeeds(self):
        """HTTP 429 on first attempt, success on second."""
        facts_json = _valid_fact_json()

        # First call: 429, second call: 200
        error_response = httpx.Response(
            status_code=429,
            headers={"retry-after": "0"},
            request=httpx.Request("POST", "https://test"),
        )
        success_response = httpx.Response(
            status_code=200,
            json=_anthropic_response(facts_json),
            request=httpx.Request("POST", "https://test"),
        )

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(
            side_effect=[
                httpx.HTTPStatusError(
                    "429", request=error_response.request, response=error_response
                ),
                success_response,
            ]
        )

        svc = InferenceService(settings=_settings(), http_client=client)
        with patch.object(InferenceService, "_sleep", new_callable=AsyncMock):
            result = await svc.extract_facts(_sample_lines())

        assert len(result) == 1
        assert client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_http_500_retries_then_succeeds(self):
        """HTTP 500 on first attempt, success on second."""
        facts_json = _valid_fact_json()

        error_response = httpx.Response(
            status_code=500,
            request=httpx.Request("POST", "https://test"),
        )
        success_response = httpx.Response(
            status_code=200,
            json=_anthropic_response(facts_json),
            request=httpx.Request("POST", "https://test"),
        )

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(
            side_effect=[
                httpx.HTTPStatusError(
                    "500", request=error_response.request, response=error_response
                ),
                success_response,
            ]
        )

        svc = InferenceService(settings=_settings(), http_client=client)
        with patch.object(InferenceService, "_sleep", new_callable=AsyncMock):
            result = await svc.extract_facts(_sample_lines())

        assert len(result) == 1
        assert client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_http_500_retries_exhausted(self):
        """HTTP 500 on all 3 attempts — raises InferenceApiError."""
        error_response = httpx.Response(
            status_code=500,
            request=httpx.Request("POST", "https://test"),
        )

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "500", request=error_response.request, response=error_response
            )
        )

        svc = InferenceService(
            settings=_settings(llm_max_attempts=3), http_client=client
        )
        with patch.object(InferenceService, "_sleep", new_callable=AsyncMock):
            with pytest.raises(InferenceApiError, match="unavailable after 3 attempts"):
                await svc.extract_facts(_sample_lines())

        assert client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_http_502_retries(self):
        """HTTP 502 triggers retry."""
        facts_json = _valid_fact_json()

        error_response = httpx.Response(
            status_code=502,
            request=httpx.Request("POST", "https://test"),
        )
        success_response = httpx.Response(
            status_code=200,
            json=_anthropic_response(facts_json),
            request=httpx.Request("POST", "https://test"),
        )

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(
            side_effect=[
                httpx.HTTPStatusError(
                    "502", request=error_response.request, response=error_response
                ),
                success_response,
            ]
        )

        svc = InferenceService(settings=_settings(), http_client=client)
        with patch.object(InferenceService, "_sleep", new_callable=AsyncMock):
            result = await svc.extract_facts(_sample_lines())

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_http_503_retries(self):
        """HTTP 503 triggers retry."""
        facts_json = _valid_fact_json()

        error_response = httpx.Response(
            status_code=503,
            request=httpx.Request("POST", "https://test"),
        )
        success_response = httpx.Response(
            status_code=200,
            json=_anthropic_response(facts_json),
            request=httpx.Request("POST", "https://test"),
        )

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(
            side_effect=[
                httpx.HTTPStatusError(
                    "503", request=error_response.request, response=error_response
                ),
                success_response,
            ]
        )

        svc = InferenceService(settings=_settings(), http_client=client)
        with patch.object(InferenceService, "_sleep", new_callable=AsyncMock):
            result = await svc.extract_facts(_sample_lines())

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_http_504_retries(self):
        """HTTP 504 triggers retry."""
        facts_json = _valid_fact_json()

        error_response = httpx.Response(
            status_code=504,
            request=httpx.Request("POST", "https://test"),
        )
        success_response = httpx.Response(
            status_code=200,
            json=_anthropic_response(facts_json),
            request=httpx.Request("POST", "https://test"),
        )

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(
            side_effect=[
                httpx.HTTPStatusError(
                    "504", request=error_response.request, response=error_response
                ),
                success_response,
            ]
        )

        svc = InferenceService(settings=_settings(), http_client=client)
        with patch.object(InferenceService, "_sleep", new_callable=AsyncMock):
            result = await svc.extract_facts(_sample_lines())

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_http_401_no_retry(self):
        """HTTP 401 raises InferenceApiError immediately — no retry."""
        error_response = httpx.Response(
            status_code=401,
            request=httpx.Request("POST", "https://test"),
        )

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "401", request=error_response.request, response=error_response
            )
        )

        svc = InferenceService(settings=_settings(), http_client=client)
        with pytest.raises(InferenceApiError, match="non-retryable HTTP 401"):
            await svc.extract_facts(_sample_lines())

        # Must NOT retry — only 1 call
        assert client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_http_400_no_retry(self):
        """HTTP 400 raises InferenceApiError immediately — no retry."""
        error_response = httpx.Response(
            status_code=400,
            request=httpx.Request("POST", "https://test"),
        )

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "400", request=error_response.request, response=error_response
            )
        )

        svc = InferenceService(settings=_settings(), http_client=client)
        with pytest.raises(InferenceApiError, match="non-retryable HTTP 400"):
            await svc.extract_facts(_sample_lines())

        assert client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_timeout_retries_then_succeeds(self):
        """Network timeout on first attempt, success on second."""
        facts_json = _valid_fact_json()

        success_response = httpx.Response(
            status_code=200,
            json=_anthropic_response(facts_json),
            request=httpx.Request("POST", "https://test"),
        )

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(
            side_effect=[
                httpx.TimeoutException("Connection timed out"),
                success_response,
            ]
        )

        svc = InferenceService(settings=_settings(), http_client=client)
        with patch.object(InferenceService, "_sleep", new_callable=AsyncMock):
            result = await svc.extract_facts(_sample_lines())

        assert len(result) == 1
        assert client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_timeout_retries_exhausted(self):
        """Network timeout on all 3 attempts — raises InferenceApiError."""
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(
            side_effect=httpx.TimeoutException("Connection timed out")
        )

        svc = InferenceService(
            settings=_settings(llm_max_attempts=3), http_client=client
        )
        with patch.object(InferenceService, "_sleep", new_callable=AsyncMock):
            with pytest.raises(InferenceApiError, match="unavailable after 3 attempts"):
                await svc.extract_facts(_sample_lines())

        assert client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_connect_error_retries(self):
        """Connection error triggers retry."""
        facts_json = _valid_fact_json()

        success_response = httpx.Response(
            status_code=200,
            json=_anthropic_response(facts_json),
            request=httpx.Request("POST", "https://test"),
        )

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(
            side_effect=[
                httpx.ConnectError("Connection refused"),
                success_response,
            ]
        )

        svc = InferenceService(settings=_settings(), http_client=client)
        with patch.object(InferenceService, "_sleep", new_callable=AsyncMock):
            result = await svc.extract_facts(_sample_lines())

        assert len(result) == 1
        assert client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_after_header_respected(self):
        """HTTP 429 with Retry-After header — backoff uses that value."""
        facts_json = _valid_fact_json()

        error_response = httpx.Response(
            status_code=429,
            headers={"retry-after": "5"},
            request=httpx.Request("POST", "https://test"),
        )
        success_response = httpx.Response(
            status_code=200,
            json=_anthropic_response(facts_json),
            request=httpx.Request("POST", "https://test"),
        )

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(
            side_effect=[
                httpx.HTTPStatusError(
                    "429", request=error_response.request, response=error_response
                ),
                success_response,
            ]
        )

        mock_sleep = AsyncMock()
        svc = InferenceService(settings=_settings(), http_client=client)
        with patch.object(InferenceService, "_sleep", mock_sleep):
            await svc.extract_facts(_sample_lines())

        # _sleep should have been called with the Retry-After value
        mock_sleep.assert_called_once_with(5.0)

    @pytest.mark.asyncio
    async def test_unknown_http_error_no_retry(self):
        """An unexpected HTTP status (e.g. 418) should not retry."""
        error_response = httpx.Response(
            status_code=418,
            request=httpx.Request("POST", "https://test"),
        )

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "418", request=error_response.request, response=error_response
            )
        )

        svc = InferenceService(settings=_settings(), http_client=client)
        with pytest.raises(InferenceApiError, match="unexpected HTTP 418"):
            await svc.extract_facts(_sample_lines())

        assert client.post.call_count == 1


# ── Backoff delay ────────────────────────────────────────────────


class TestBackoffDelay:
    def test_first_attempt_range(self):
        """Attempt 0 should produce delay in range [0.5, 1.5] (2^0 * jitter)."""
        delays = [InferenceService._backoff_delay(0) for _ in range(100)]
        assert all(0.5 <= d <= 1.5 for d in delays)

    def test_second_attempt_range(self):
        """Attempt 1 should produce delay in range [1.0, 3.0] (2^1 * jitter)."""
        delays = [InferenceService._backoff_delay(1) for _ in range(100)]
        assert all(1.0 <= d <= 3.0 for d in delays)

    def test_retry_after_header_takes_precedence(self):
        response = httpx.Response(
            status_code=429,
            headers={"retry-after": "10"},
            request=httpx.Request("POST", "https://test"),
        )
        assert InferenceService._backoff_delay(0, response) == 10.0

    def test_invalid_retry_after_falls_back(self):
        response = httpx.Response(
            status_code=429,
            headers={"retry-after": "not-a-number"},
            request=httpx.Request("POST", "https://test"),
        )
        delay = InferenceService._backoff_delay(0, response)
        # Falls back to exponential: 2^0 * jitter ∈ [0.5, 1.5]
        assert 0.5 <= delay <= 1.5


# ── Prompt construction (end-to-end format check) ───────────────


class TestPromptConstruction:
    """Verify that the user message sent to the LLM matches §9.5 format."""

    @pytest.mark.asyncio
    async def test_user_message_format(self):
        lines = [
            ParsedLine(canonical_key="p", text="Alice, CEO"),
            ParsedLine(canonical_key="fn", text="Engineering"),
            ParsedLine(canonical_key="rel", text="Bob > Alice"),
            ParsedLine(canonical_key="t", text="Kubernetes"),
        ]

        facts_json = _valid_fact_json()
        client = _mock_client_with_response(_anthropic_response(facts_json))
        svc = InferenceService(settings=_settings(), http_client=client)

        await svc.extract_facts(lines)

        call_kwargs = client.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        user_msg = body["messages"][0]["content"]

        expected = "p: Alice, CEO\nfn: Engineering\nrel: Bob > Alice\nt: Kubernetes"
        assert user_msg == expected

    @pytest.mark.asyncio
    async def test_system_prompt_is_set(self):
        facts_json = _valid_fact_json()
        client = _mock_client_with_response(_anthropic_response(facts_json))
        svc = InferenceService(settings=_settings(), http_client=client)

        await svc.extract_facts(_sample_lines())

        call_kwargs = client.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["system"] == SYSTEM_PROMPT


# ── Unit tests: _build_raw_system_prompt ────────────────────────


class TestBuildRawSystemPrompt:
    def test_no_context_returns_raw_prompt_unchanged(self):
        result = _build_raw_system_prompt(None)
        assert result == RAW_SYSTEM_PROMPT

    def test_with_context_appends_delimited_section(self):
        context = "Known people: Jane Doe (CTO)\nKnown tech: Kubernetes"
        result = _build_raw_system_prompt(context)
        assert result.startswith(RAW_SYSTEM_PROMPT)
        assert "=== COMPANY CONTEXT ===" in result
        assert context in result
        assert "=== END CONTEXT ===" in result

    def test_with_context_preserves_prompt_before_context(self):
        context = "Some context"
        result = _build_raw_system_prompt(context)
        # The raw prompt text should appear in full before the context section
        idx_prompt_end = result.index("\n=== COMPANY CONTEXT ===")
        assert result[:idx_prompt_end] == RAW_SYSTEM_PROMPT


# ── Integration tests: InferenceService.extract_facts_raw ───────


class TestExtractFactsRaw:
    """Tests for the raw text extraction entry point."""

    @pytest.mark.asyncio
    async def test_valid_raw_text_returns_facts(self):
        """extract_facts_raw with valid raw text returns list of LLMInferredFact."""
        facts_json = _valid_fact_json([
            {"category": "person", "value": "Jane Doe"},
            {"category": "technology", "value": "Python"},
        ])
        client = _mock_client_with_response(_anthropic_response(facts_json))
        svc = InferenceService(settings=_settings(), http_client=client)

        result = await svc.extract_facts_raw("Met with Jane Doe. They use Python.")

        assert len(result) == 2
        assert all(isinstance(f, LLMInferredFact) for f in result)
        assert result[0].category == "person"
        assert result[1].value == "Python"

    @pytest.mark.asyncio
    async def test_empty_raw_text_returns_empty_list(self):
        """extract_facts_raw with empty raw_text returns empty list, no LLM call."""
        client = _mock_client_with_response(_anthropic_response("[]"))
        svc = InferenceService(settings=_settings(), http_client=client)

        result = await svc.extract_facts_raw("")

        assert result == []
        client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_whitespace_only_raw_text_returns_empty_list(self):
        """extract_facts_raw with whitespace-only raw_text returns empty list."""
        client = _mock_client_with_response(_anthropic_response("[]"))
        svc = InferenceService(settings=_settings(), http_client=client)

        result = await svc.extract_facts_raw("   \n\t  ")

        assert result == []
        client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_with_context_injects_into_system_prompt(self):
        """Company context appears in system prompt, not in user message."""
        facts_json = _valid_fact_json()
        client = _mock_client_with_response(_anthropic_response(facts_json))
        svc = InferenceService(settings=_settings(), http_client=client)
        context = "Known people: Alice (CEO)"

        await svc.extract_facts_raw("Met with Bob today.", context)

        call_kwargs = client.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        system = body["system"]
        user_msg = body["messages"][0]["content"]
        # Context must be in system prompt
        assert "=== COMPANY CONTEXT ===" in system
        assert context in system
        # Context must NOT be in user message
        assert context not in user_msg
        # User message is just the raw text
        assert user_msg == "Met with Bob today."

    @pytest.mark.asyncio
    async def test_without_context_uses_raw_prompt_unmodified(self):
        """Without context, system prompt is RAW_SYSTEM_PROMPT unmodified."""
        facts_json = _valid_fact_json()
        client = _mock_client_with_response(_anthropic_response(facts_json))
        svc = InferenceService(settings=_settings(), http_client=client)

        await svc.extract_facts_raw("Some raw text.")

        call_kwargs = client.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["system"] == RAW_SYSTEM_PROMPT
        assert body["messages"][0]["content"] == "Some raw text."

    @pytest.mark.asyncio
    async def test_uses_raw_prompt_not_tagged_prompt(self):
        """extract_facts_raw uses RAW_SYSTEM_PROMPT, not SYSTEM_PROMPT."""
        facts_json = _valid_fact_json()
        client = _mock_client_with_response(_anthropic_response(facts_json))
        svc = InferenceService(settings=_settings(), http_client=client)

        await svc.extract_facts_raw("Some text.")

        call_kwargs = client.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["system"] != SYSTEM_PROMPT
        assert body["system"] == RAW_SYSTEM_PROMPT


class TestExtractFactsRawValidation:
    """Validation failure tests for extract_facts_raw."""

    @pytest.mark.asyncio
    async def test_malformed_json(self):
        client = _mock_client_with_response(
            _anthropic_response("not valid json {{{")
        )
        svc = InferenceService(settings=_settings(), http_client=client)
        with pytest.raises(InferenceValidationError, match="invalid JSON"):
            await svc.extract_facts_raw("Some text.")

    @pytest.mark.asyncio
    async def test_empty_array(self):
        client = _mock_client_with_response(_anthropic_response("[]"))
        svc = InferenceService(settings=_settings(), http_client=client)
        with pytest.raises(InferenceValidationError, match="empty array"):
            await svc.extract_facts_raw("Some text.")

    @pytest.mark.asyncio
    async def test_missing_category(self):
        bad_json = json.dumps([{"value": "Alice"}])
        client = _mock_client_with_response(_anthropic_response(bad_json))
        svc = InferenceService(settings=_settings(), http_client=client)
        with pytest.raises(InferenceValidationError, match="validation failed"):
            await svc.extract_facts_raw("Some text.")

    @pytest.mark.asyncio
    async def test_missing_value(self):
        bad_json = json.dumps([{"category": "person"}])
        client = _mock_client_with_response(_anthropic_response(bad_json))
        svc = InferenceService(settings=_settings(), http_client=client)
        with pytest.raises(InferenceValidationError, match="validation failed"):
            await svc.extract_facts_raw("Some text.")

    @pytest.mark.asyncio
    async def test_unknown_category(self):
        bad_json = json.dumps([{"category": "bogus", "value": "whatever"}])
        client = _mock_client_with_response(_anthropic_response(bad_json))
        svc = InferenceService(settings=_settings(), http_client=client)
        with pytest.raises(InferenceValidationError, match="validation failed"):
            await svc.extract_facts_raw("Some text.")

    @pytest.mark.asyncio
    async def test_relationship_missing_subordinate(self):
        bad_json = json.dumps([
            {"category": "relationship", "value": "reports-to", "manager": "Alice"}
        ])
        client = _mock_client_with_response(_anthropic_response(bad_json))
        svc = InferenceService(settings=_settings(), http_client=client)
        with pytest.raises(InferenceValidationError, match="validation failed"):
            await svc.extract_facts_raw("Some text.")

    @pytest.mark.asyncio
    async def test_relationship_missing_manager(self):
        bad_json = json.dumps([
            {"category": "relationship", "value": "reports-to", "subordinate": "Bob"}
        ])
        client = _mock_client_with_response(_anthropic_response(bad_json))
        svc = InferenceService(settings=_settings(), http_client=client)
        with pytest.raises(InferenceValidationError, match="validation failed"):
            await svc.extract_facts_raw("Some text.")


class TestExtractFactsRawRetry:
    """Retry behaviour for extract_facts_raw."""

    @pytest.mark.asyncio
    async def test_api_failure_retries_then_raises(self):
        """API failure → retries exhausted → raises InferenceApiError."""
        error_response = httpx.Response(
            status_code=500,
            request=httpx.Request("POST", "https://test"),
        )
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "500", request=error_response.request, response=error_response
            )
        )

        svc = InferenceService(
            settings=_settings(llm_max_attempts=3), http_client=client
        )
        with patch.object(InferenceService, "_sleep", new_callable=AsyncMock):
            with pytest.raises(InferenceApiError, match="unavailable after 3 attempts"):
                await svc.extract_facts_raw("Some text.")

        assert client.post.call_count == 3


class TestExtractFactsRawOpenAI:
    """Verify extract_facts_raw works with OpenAI provider."""

    @pytest.mark.asyncio
    async def test_openai_raw_uses_raw_system_prompt(self):
        facts_json = _valid_fact_json()
        client = _mock_client_with_response(_openai_response(facts_json))
        svc = InferenceService(
            settings=_settings(llm_provider="openai"), http_client=client
        )

        await svc.extract_facts_raw("Some raw text.")

        call_kwargs = client.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][0]["content"] == RAW_SYSTEM_PROMPT
        assert body["messages"][1]["role"] == "user"
        assert body["messages"][1]["content"] == "Some raw text."
