"""Fuzzy string similarity scoring.

Provides a normalized similarity score (0.0–1.0) using the standard
library's ``difflib.SequenceMatcher``.  No external dependencies.

Used by:
  - PersonService.resolve_person() — tiebreak when multiple name matches exist
  - ReviewService.list_pending() — disambiguation candidate ranking (Unit 4)
"""

from difflib import SequenceMatcher


def similarity_score(a: str, b: str) -> float:
    """Return a normalized similarity score between two strings.

    Normalizes by lowercasing and stripping whitespace before comparison.
    Returns a float in [0.0, 1.0] where 1.0 means identical (after
    normalization).
    """
    a_norm = a.strip().lower()
    b_norm = b.strip().lower()
    return SequenceMatcher(None, a_norm, b_norm).ratio()
