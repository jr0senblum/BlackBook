"""PrefixParserService — normalizes raw source text into a typed ParsedSource.

Pure computation: no I/O, no database, no LLM.  Called exclusively by
IngestionService.  See REQUIREMENTS.md §9.6 for the full contract.
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures — the contract boundary between parsing and the pipeline
# ---------------------------------------------------------------------------


@dataclass
class ParsedLine:
    """A single normalized line of source content."""

    canonical_key: str  # e.g. "p", "fn", "rel", "kp", "n"
    text: str  # content after the colon, stripped


@dataclass
class ParsedSource:
    """Fully parsed source document."""

    nc: str | None = None  # new company name
    c: str | None = None  # existing company name (exact match)
    cid: str | None = None  # existing company ID (exact match)
    who: str | None = None  # contact / source person
    date: str | None = None  # date of interaction
    src: str | None = None  # provenance label
    lines: list[ParsedLine] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Canonical prefix map — from REQUIREMENTS.md §6.1
# ---------------------------------------------------------------------------

CANONICAL_MAP: dict[str, str] = {
    # Routing keys
    "nc": "nc",
    "c": "c",
    "cid": "cid",
    # Metadata keys
    "contact": "who",
    "from": "who",
    "d": "date",
    "when": "date",
    "source": "src",
    "via": "src",
    # Content keys
    "person": "p",
    "pe": "p",
    "reports": "rel",
    "under": "rel",
    "func": "fn",
    "area": "fn",
    "team": "fn",
    "tech": "t",
    "stack": "t",
    "process": "proc",
    "how": "proc",
    # CGKRA
    "cs": "cs",
    "cur": "cs",
    "current": "cs",
    "gw": "gw",
    "well": "gw",
    "kp": "kp",
    "prob": "kp",
    "problem": "kp",
    "rm": "rm",
    "road": "rm",
    "roadmap": "rm",
    "aop": "aop",
    # SWOT
    "str": "s",
    "strength": "s",
    "+": "s",
    "weak": "w",
    "weakness": "w",
    "-": "w",
    "opp": "o",
    "opportunity": "o",
    "threat": "th",
    "risk": "th",
    # Action items
    "action": "a",
    "todo": "a",
    "do": "a",
    # Plain note
    "note": "n",
    # Canonical self-mappings for keys that are their own alias
    "who": "who",
    "date": "date",
    "src": "src",
    "p": "p",
    "rel": "rel",
    "fn": "fn",
    "t": "t",
    "proc": "proc",
    "s": "s",
    "w": "w",
    "o": "o",
    "th": "th",
    "a": "a",
    "n": "n",
}

ROUTING_KEYS: set[str] = {"nc", "c", "cid"}
METADATA_KEYS: set[str] = {"who", "date", "src"}

# Regex: match an optional prefix before the first colon.
# Captures the prefix (group 1) and the text after the colon (group 2).
_PREFIX_RE = re.compile(r"^([^:]+):(.*)", re.DOTALL)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def parse(raw_text: str) -> ParsedSource:
    """Parse raw source text into a typed ParsedSource struct.

    This is a synchronous, pure-computation function (no I/O).
    See REQUIREMENTS.md §9.6 for the full contract.
    """
    result = ParsedSource()

    for line in raw_text.split("\n"):
        # Discard blank lines.
        stripped = line.strip()
        if not stripped:
            continue

        match = _PREFIX_RE.match(stripped)
        if match is None:
            # No colon at all — treat as plain note with full line.
            result.lines.append(ParsedLine(canonical_key="n", text=stripped))
            continue

        raw_prefix = match.group(1).strip().lower()
        text_after_colon = match.group(2).strip()

        canonical = CANONICAL_MAP.get(raw_prefix)

        if canonical is None:
            # Unrecognized prefix — treat as plain note with full line.
            logger.warning(
                "Unrecognized prefix '%s' — treating as plain note", raw_prefix
            )
            result.lines.append(ParsedLine(canonical_key="n", text=stripped))
            continue

        # Routing keys → store in dedicated fields, NOT in lines.
        if canonical in ROUTING_KEYS:
            setattr(result, canonical, text_after_colon)
            continue

        # Metadata keys → store in dedicated fields, NOT in lines.
        if canonical in METADATA_KEYS:
            setattr(result, canonical, text_after_colon)
            continue

        # rel: lines — validate > separator is present.
        if canonical == "rel":
            if ">" not in text_after_colon:
                # Malformed rel line — emit as plain note with full line.
                result.lines.append(ParsedLine(canonical_key="n", text=stripped))
                continue

        # All other canonical keys — emit into lines.
        result.lines.append(ParsedLine(canonical_key=canonical, text=text_after_colon))

    return result
