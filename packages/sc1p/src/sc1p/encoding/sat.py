"""Precedence variables for the SAT encoding of SC1P.

One Boolean variable ``p_{a,b}`` per column pair ``a < b``, true when column
``a`` comes before column ``b``; ``p_{b,a}`` is its negation. Indices here are
0-based; PySAT literals add 1.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import cmp_to_key

from sc1p.types import Permutation


def num_pairs(n: int) -> int:
    return n * (n - 1) // 2


def pair_index(a: int, b: int, n: int) -> int:
    """Index of ``v(a, b)`` for ``a < b``, row-major over the upper triangle."""
    return a * (2 * n - a - 1) // 2 + (b - a) - 1


def transitivity_triples(n: int) -> Iterator[tuple[int, int, int]]:
    """``(ab, bc, ac)`` indices for every triple ``a < b < c``."""
    for a in range(n - 2):
        for b in range(a + 1, n - 1):
            ab = pair_index(a, b, n)
            for c in range(b + 1, n):
                yield ab, pair_index(b, c, n), pair_index(a, c, n)


def is_before_from(
    values: dict[int, bool], a: int, b: int, n: int, one_indexed: bool = False
) -> bool:
    offset = 1 if one_indexed else 0
    if a < b:
        return bool(values.get(pair_index(a, b, n) + offset, False))
    return not values.get(pair_index(b, a, n) + offset, False)


def extract_perm(values: dict[int, bool], n: int, one_indexed: bool = False) -> Permutation:
    """Column order encoded by a transitive assignment of the precedence variables."""
    return sorted(
        range(n),
        key=cmp_to_key(lambda a, b: -1 if is_before_from(values, a, b, n, one_indexed) else 1),
    )
