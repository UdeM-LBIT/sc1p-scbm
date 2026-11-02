"""Tests for SC1P verification, encoding helpers, and ternary validation."""

from __future__ import annotations

import pytest

import sc1p
from sc1p import validate_ternary
from sc1p.encoding import extract_perm, num_pairs, pair_index


def test_validate_ternary_dims(paper_matrix):
    assert validate_ternary(paper_matrix) == (6, 5)


def test_validate_ternary_rejects_ragged():
    with pytest.raises(ValueError):
        validate_ternary([[0, 1], [0]])


def test_validate_ternary_rejects_non_ternary():
    with pytest.raises(ValueError):
        validate_ternary([[0, 1, 3]])


def test_pair_index_is_bijective():
    n = 6
    seen = set()
    for a in range(n):
        for b in range(a + 1, n):
            idx = pair_index(a, b, n)
            assert 0 <= idx < num_pairs(n)
            seen.add(idx)
    assert len(seen) == num_pairs(n)


def test_verify_accepts_valid_permutation():
    matrix = [[1, 1, 0], [0, 1, 1]]
    assert sc1p.verify(matrix, [0, 1, 2])


def test_verify_rejects_broken_permutation():
    matrix = [[1, 0, 1]]
    assert not sc1p.verify(matrix, [0, 1, 2])
    assert sc1p.verify(matrix, [0, 2, 1])


def test_extract_perm_roundtrip():
    n = 3
    values = {
        pair_index(0, 1, n): True,
        pair_index(0, 2, n): True,
        pair_index(1, 2, n): True,
    }
    assert extract_perm(values, n) == [0, 1, 2]
