"""Tests for fuzzy_match.similarity_score().

Covers: identical, disjoint, partial, case-insensitive, abbreviation, and
empty-string inputs.  The empty-string case is exercised by the malformed
relationship fallback in ReviewService.list_pending().
"""

import pytest

from app.services.fuzzy_match import similarity_score


def test_exact_match_score_1() -> None:
    """Identical strings return 1.0."""
    assert similarity_score("Kubernetes", "Kubernetes") == 1.0


def test_no_overlap_score_0() -> None:
    """Completely different strings (no shared characters) return 0.0."""
    assert similarity_score("aaa", "zzz") == 0.0


def test_partial_match() -> None:
    """'Eng' vs 'Engineering' returns a moderate score (SequenceMatcher ≈ 0.43)."""
    score = similarity_score("Eng", "Engineering")
    # Character-level match is moderate — assert > 0.3 not > 0.5
    assert score > 0.3
    assert score < 1.0


def test_case_insensitive() -> None:
    """Case differences are ignored — 'kubernetes' vs 'Kubernetes' -> 1.0."""
    assert similarity_score("kubernetes", "Kubernetes") == 1.0


def test_abbreviation() -> None:
    """'k8s' vs 'Kubernetes' scores low (≈ 0.31); character-level matching
    cannot infer abbreviation semantics."""
    score = similarity_score("k8s", "Kubernetes")
    assert score < 0.4


def test_empty_string_input() -> None:
    """Empty-string inputs behave as expected per SequenceMatcher semantics.

    This code path is exercised by the malformed relationship fallback in
    ReviewService._compute_candidates() when inferred_value lacks '>':
    every person's name is scored against "" for the manager sub-list.
    """
    # Non-empty vs empty → 0.0
    assert similarity_score("Alice", "") == 0.0
    # Empty vs non-empty → 0.0
    assert similarity_score("", "Alice") == 0.0
    # Both empty → 1.0 (SequenceMatcher considers two empty strings identical)
    assert similarity_score("", "") == 1.0
