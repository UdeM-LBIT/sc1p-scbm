from __future__ import annotations

from sc1p.types import Matrix

TERNARY_VALUES = frozenset({0, 1, 2})


def validate_ternary(matrix: Matrix) -> tuple[int, int]:
    """Return ``(m, n)`` after checking that *matrix* is rectangular over ``{0, 1, 2}``.

    Raises:
        ValueError: a row has the wrong length or a cell is not 0, 1 or 2.
    """
    m = len(matrix)
    n = len(matrix[0]) if m else 0
    for i, row in enumerate(matrix):
        if len(row) != n:
            raise ValueError(f"row {i} has length {len(row)}, expected {n}")
        for j, cell in enumerate(row):
            if cell not in TERNARY_VALUES:
                raise ValueError(f"cell ({i}, {j}) is {cell!r}, expected 0, 1 or 2")
    return m, n
