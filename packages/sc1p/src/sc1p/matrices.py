from __future__ import annotations

from typing import TYPE_CHECKING

from sc1p.types import Matrix

if TYPE_CHECKING:
    import random


def sc1p_example() -> Matrix:
    """A 6 x 5 matrix with SC1P and 12 valid column orders."""
    return [
        [0, 1, 0, 1, 0],
        [1, 2, 0, 2, 1],
        [0, 2, 1, 2, 0],
        [1, 0, 0, 0, 1],
        [2, 1, 1, 0, 2],
        [2, 0, 0, 1, 2],
    ]


def random_matrix(m: int, n: int, p1: float, p0: float, rng: random.Random | None = None) -> Matrix:
    """Cells are ``1`` with probability *p1*, ``0`` with *p0*, and ``2`` otherwise.

    Without *rng*, draws come from the global :mod:`random` state.
    """
    import random

    draw = rng.random if rng is not None else random.random
    matrix = []
    for _ in range(m):
        row = []
        for _ in range(n):
            r = draw()
            row.append(1 if r < p1 else 0 if r < p1 + p0 else 2)
        matrix.append(row)
    return matrix
