"""IngestionService — orchestrates upload → parsing → routing → LLM extraction → fact persistence."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

from app.config import Settings
from app.exceptions import (
    InferenceApiError,
    InferenceValidationError,
    RoutingError,
    SourceNotFailedError,
    SourceNotFoundError,
)
from app.models.base import Source
from app.repositories.company_repository import CompanyRepository
from app.repositories.inferred_fact_repository import InferredFactRepository
from app.repositories.source_repository import SourceRepository
from app.services.prefix_parser_service import ParsedLine, parse

if TYPE_CHECKING:
    from app.schemas.inferred_fact import LLMInferredFact

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol interfaces for services that are not yet implemented.
# IngestionService depends on InferenceService (Unit 2) and ReviewService
# (Unit 5). These protocols define the minimal contract so IngestionService
# can be implemented and tested with mocks before those units exist.
# ---------------------------------------------------------------------------


class InferenceServiceProtocol(Protocol):
    async def extract_facts(self, lines: list[ParsedLine]) -> list[Any]: ...
    async def extract_facts_raw(
        self, raw_text: str, company_context: str | None = None
    ) -> list[Any]: ...


class ReviewServiceProtocol(Protocol):
    async def save_facts(
        self,
        source_id: str | UUID,
        company_id: str | UUID,
        facts: list[Any],
        lines: list[ParsedLine] | None = None,
        raw_lines: list[str] | None = None,
    ) -> None: ...


class IngestionQueueProtocol(Protocol):
    async def enqueue(self, source_id: str) -> None: ...


# ---------------------------------------------------------------------------
# Filename sanitization (§8)
# ---------------------------------------------------------------------------


def sanitize_filename(name: str) -> str:
    """Strip characters outside [a-zA-Z0-9._-] and truncate to 100 chars."""
    sanitized = re.sub(r"[^a-zA-Z0-9._\-]", "", name)
    return sanitized[:100]


# ---------------------------------------------------------------------------
# IngestionService
# ---------------------------------------------------------------------------


class IngestionService:
    def __init__(
        self,
        *,
        source_repo: SourceRepository,
        inferred_fact_repo: InferredFactRepository,
        company_repo: CompanyRepository,
        inference_service: InferenceServiceProtocol,
        review_service: ReviewServiceProtocol,
        ingestion_queue: IngestionQueueProtocol,
        settings: Settings,
    ):
        self._source_repo = source_repo
        self._inferred_fact_repo = inferred_fact_repo
        self._company_repo = company_repo
        self._inference_service = inference_service
        self._review_service = review_service
        self._ingestion_queue = ingestion_queue
        self._settings = settings

    # ── Upload (synchronous part) ────────────────────────────────

    async def ingest_upload(
        self,
        file_content: str,
        filename: str,
        company_id: str | None = None,
    ) -> str:
        """Parse raw text, apply company routing, create Source record.

        Returns the source_id (as string). Actual LLM processing happens
        asynchronously via the background worker.
        """
        parsed = parse(file_content)

        # --- Company routing (§9.7) ---
        resolved_company_id = await self._resolve_company(parsed, company_id)

        # --- Create Source record ---
        safe_name = sanitize_filename(filename)
        source = await self._source_repo.create(
            company_id=resolved_company_id,
            type="upload",
            filename_or_subject=filename,
            raw_content=file_content,
            who=parsed.who,
            interaction_date=parsed.date,
            src=parsed.src,
        )

        # Compute file_path and update the Source record.
        # Path is relative to data_dir: "sources/{company_id}/{source_id}_{filename}"
        rel_path = os.path.join(
            "sources", str(resolved_company_id), f"{source.id}_{safe_name}"
        )
        await self._source_repo.update_file_path(source.id, rel_path)

        # --- Save uploaded file to disk ---
        await self._save_file(
            company_id=resolved_company_id,
            source_id=source.id,
            filename=filename,
            content=file_content,
        )

        return str(source.id)

    # ── Process source (async, called by worker) ─────────────────

    async def process_source(self, source_id: str) -> None:
        """Load source, call LLM, persist facts. Called by the background worker.

        Detects extraction mode based on parsed lines:
        - **Tagged**: all lines have explicit prefixes → extract_facts()
        - **Raw**: all lines are defaulted (no prefix) → extract_facts_raw()
        - **Hybrid**: mix of tagged and defaulted → both passes, fail-all on error
        - **No lines**: routing/metadata only → mark processed with zero facts
        """
        sid = UUID(source_id)

        # Load and mark processing
        source = await self._source_repo.get_by_id(sid)
        if source is None:
            raise SourceNotFoundError(f"Source not found: {source_id}")
        await self._source_repo.update_status(sid, status="processing")

        try:
            # Re-parse to get content lines (excludes routing/metadata)
            parsed = parse(source.raw_content)

            # No content lines — mark processed with zero facts
            if not parsed.lines:
                await self._source_repo.update_status(sid, status="processed")
                return

            # Mode detection
            tagged_lines = [l for l in parsed.lines if not l.defaulted]
            untagged_lines = [l for l in parsed.lines if l.defaulted]
            has_tagged = len(tagged_lines) > 0
            has_untagged = len(untagged_lines) > 0

            if has_tagged and not has_untagged:
                # Tagged mode — all lines have explicit prefixes
                facts = await self._inference_service.extract_facts(tagged_lines)
                await self._review_service.save_facts(
                    source.id, source.company_id, facts, lines=tagged_lines
                )

            elif not has_tagged and has_untagged:
                # Raw mode — all lines are defaulted
                context = await self._build_company_context(source.company_id)
                raw_text = "\n".join(l.text for l in untagged_lines)
                facts = await self._inference_service.extract_facts_raw(
                    raw_text, context
                )
                await self._review_service.save_facts(
                    source.id, source.company_id, facts,
                    raw_lines=[l.text for l in untagged_lines],
                )

            else:
                # Hybrid mode — mix of tagged and untagged
                # Pass 1: tagged extraction
                tagged_facts = await self._inference_service.extract_facts(
                    tagged_lines
                )

                # Pass 2: raw extraction
                context = await self._build_company_context(source.company_id)
                raw_text = "\n".join(l.text for l in untagged_lines)
                raw_facts = await self._inference_service.extract_facts_raw(
                    raw_text, context
                )

                # Combine and persist (dedup at save time handles overlap)
                all_facts = tagged_facts + raw_facts
                await self._review_service.save_facts(
                    source.id, source.company_id, all_facts,
                    lines=tagged_lines,
                    raw_lines=[l.text for l in untagged_lines],
                )

            # Mark processed
            await self._source_repo.update_status(sid, status="processed")

        except InferenceValidationError as exc:
            logger.warning(
                "Inference validation failed for source %s: %s",
                source_id,
                exc.message,
            )
            await self._source_repo.update_status(
                sid,
                status="failed",
                error=exc.message,
                raw_llm_response=exc.raw_response,
            )

        except InferenceApiError as exc:
            logger.warning(
                "Inference API failed for source %s: %s",
                source_id,
                exc.message,
            )
            await self._source_repo.update_status(
                sid, status="failed", error=exc.message
            )

    # ── Retry ────────────────────────────────────────────────────

    async def retry_source(self, source_id: str) -> None:
        """Reset a failed source to pending and enqueue for reprocessing."""
        sid = UUID(source_id)
        source = await self._source_repo.get_by_id(sid)
        if source is None:
            raise SourceNotFoundError(f"Source not found: {source_id}")
        if source.status != "failed":
            raise SourceNotFailedError(
                f"Source status is '{source.status}', not 'failed'"
            )
        await self._source_repo.update_status(
            sid, status="pending", error=None, raw_llm_response=None
        )
        await self._ingestion_queue.enqueue(source_id)

    # ── Read-only accessors ──────────────────────────────────────

    async def get_source(self, source_id: str) -> Source:
        """Return a source by ID or raise SourceNotFoundError."""
        source = await self._source_repo.get_by_id(UUID(source_id))
        if source is None:
            raise SourceNotFoundError(f"Source not found: {source_id}")
        return source

    async def get_source_status(self, source_id: str) -> str:
        """Return the current status string for a source."""
        source = await self.get_source(source_id)
        return source.status

    async def list_sources(
        self,
        company_id: str,
        *,
        status: str = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Source], int]:
        """Delegate to SourceRepository.list_by_company."""
        return await self._source_repo.list_by_company(
            UUID(company_id), status=status, limit=limit, offset=offset
        )

    # ── Context assembly ───────────────────────────────────────────

    # Human-readable labels for context display, grouped by category.
    _CATEGORY_LABELS: dict[str, str] = {
        "person": "Known people",
        "functional-area": "Known functional areas",
        "relationship": "Known relationships",
        "technology": "Known technologies",
        "process": "Known processes",
        "cgkra-cs": "CGKRA current state",
        "cgkra-gw": "CGKRA going well",
        "cgkra-kp": "CGKRA key problems",
        "cgkra-rm": "CGKRA roadmap",
        "cgkra-aop": "CGKRA annual operating plan",
        "swot-s": "SWOT strengths",
        "swot-w": "SWOT weaknesses",
        "swot-o": "SWOT opportunities",
        "swot-th": "SWOT threats",
        "action-item": "Known action items",
        "other": "Other known facts",
    }

    async def _build_company_context(self, company_id: UUID) -> str | None:
        """Assemble company context for the LLM based on llm_context_mode.

        Returns a formatted string or None (if mode is "none" or no data exists).
        Respects the character budget from settings.llm_context_max_chars.
        Facts are added newest-first; truncation is at the fact level (never mid-fact).
        """
        company = await self._company_repo.get_by_id(company_id)
        if company is None:
            return None

        mode = company.llm_context_mode
        if mode == "none":
            return None

        budget = self._settings.llm_context_max_chars
        parts: list[str] = []
        used = 0

        # --- Accepted facts (for both "accepted_facts" and "full" modes) ---
        facts = await self._inferred_fact_repo.list_accepted_by_company(company_id)
        if facts:
            # Build groups incrementally, fact by fact (newest first from query).
            # Fact-level truncation: stop when adding the next fact would exceed budget.
            groups: dict[str, list[str]] = {}
            for fact in facts:
                cat = fact.category
                value = fact.corrected_value if fact.corrected_value is not None else fact.inferred_value

                # Compute what the output would look like after adding this fact
                trial_groups = {k: list(v) for k, v in groups.items()}
                if cat not in trial_groups:
                    trial_groups[cat] = []
                trial_groups[cat].append(value)

                trial_lines = []
                for g_cat, g_vals in trial_groups.items():
                    g_label = self._CATEGORY_LABELS.get(g_cat, g_cat)
                    trial_lines.append(f"{g_label}: {', '.join(g_vals)}")
                trial_text = "\n".join(trial_lines)

                if len(trial_text) > budget:
                    break

                # Accept this fact
                if cat not in groups:
                    groups[cat] = []
                groups[cat].append(value)

            # Format accepted groups
            for cat, values in groups.items():
                label = self._CATEGORY_LABELS.get(cat, cat)
                parts.append(f"{label}: {', '.join(values)}")
            used = len("\n".join(parts)) if parts else 0

        # --- Source content (only for "full" mode) ---
        if mode == "full":
            sources = await self._source_repo.list_processed_content(company_id)
            for filename, raw_content in sources:
                if not raw_content:
                    continue
                name = filename or "unnamed source"
                source_section = f"--- Source: {name} ---\n{raw_content}"
                # Account for the \n separator that "\n".join will add
                added_len = len(source_section) + (1 if parts else 0)
                if used + added_len > budget:
                    break
                parts.append(source_section)
                used += added_len

        if not parts:
            return None

        return "\n".join(parts)

    # ── Private helpers ──────────────────────────────────────────

    async def _resolve_company(
        self, parsed: Any, company_id_param: str | None
    ) -> UUID:
        """Apply the company routing algorithm (§9.7).

        Returns the resolved company UUID.
        Raises RoutingError on any validation or lookup failure.
        """
        nc = parsed.nc
        c = parsed.c
        cid = parsed.cid

        # company_id param acts as cid: shortcut and takes precedence
        if company_id_param is not None:
            cid = company_id_param
            # If param provided, override any in-file routing
            nc = None
            c = None

        # Validation: exactly one routing field must be set
        routing_count = sum(1 for v in (nc, c, cid) if v is not None)
        if routing_count > 1:
            raise RoutingError(
                "multiple routing prefixes present; "
                "use exactly one of nc:, c:, or cid:"
            )
        if routing_count == 0:
            raise RoutingError(
                "no company routing prefix; add nc: (new company), "
                "c: (existing company name), or cid: (existing company id)"
            )

        # Route: nc (new company)
        if nc is not None:
            existing = await self._company_repo.get_by_name_iexact(nc)
            if existing is not None:
                raise RoutingError(
                    "company name already exists; use c: to route to it"
                )
            company = await self._company_repo.create(nc)
            return company.id

        # Route: c (existing company by name)
        if c is not None:
            existing = await self._company_repo.get_by_name_iexact(c)
            if existing is None:
                raise RoutingError(
                    f"no company found with name '{c}'; "
                    "check spelling or use cid:"
                )
            return existing.id

        # Route: cid (existing company by ID)
        assert cid is not None
        try:
            cid_uuid = UUID(cid)
        except ValueError:
            raise RoutingError(f"no company found with id '{cid}'")
        existing = await self._company_repo.get_by_id(cid_uuid)
        if existing is None:
            raise RoutingError(f"no company found with id '{cid}'")
        return existing.id

    async def _save_file(
        self,
        company_id: UUID,
        source_id: UUID,
        filename: str,
        content: str,
    ) -> None:
        """Save uploaded file to BLACKBOOK_DATA_DIR/sources/{company_id}/{source_id}_{sanitized_filename}.

        File I/O is offloaded to a thread to avoid blocking the event loop.
        """
        safe_name = sanitize_filename(filename)
        dir_path = os.path.join(
            self._settings.data_dir, "sources", str(company_id)
        )
        file_path = os.path.join(dir_path, f"{source_id}_{safe_name}")
        await asyncio.to_thread(self._write_file, dir_path, file_path, content)

    @staticmethod
    def _write_file(dir_path: str, file_path: str, content: str) -> None:
        """Synchronous file write — called via asyncio.to_thread."""
        os.makedirs(dir_path, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
