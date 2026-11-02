"""Certificate check for SC1P in ``O(mn)``."""

from __future__ import annotations

from sc1p.types import Matrix, Permutation


def _row_is_segmental(row: list[int], perm: Permutation) -> bool:
    """No ``0`` strictly between the first and last ``1`` of *row* under *perm*."""
    ones = [k for k, column in enumerate(perm) if row[column] == 1]
    if len(ones) < 2:
        return True
    return all(row[perm[k]] != 0 for k in range(ones[0], ones[-1]))


def verify(matrix: Matrix, perm: Permutation) -> bool:
    return all(_row_is_segmental(row, perm) for row in matrix)
