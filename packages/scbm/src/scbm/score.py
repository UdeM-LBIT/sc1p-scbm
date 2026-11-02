"""The SCBM objective ``b(M^π)`` and its lower bound."""

from __future__ import annotations

from scbm.types import Matrix, Permutation


def block_lower_bound(matrix: Matrix) -> int:
    """Rows containing a ``1``: a lower bound on ``b(M^π)`` for every order.

    On the event matrix of a synteny tree, every row contains a ``1`` and this
    is the paper's ``λ + γ``.
    """
    return sum(1 for row in matrix if 1 in row)


def block_cost(matrix: Matrix, perm: Permutation) -> int:
    """Return ``b(M^π)``, the number of maximal blocks of ``M^π``.

    A block of a row is a substring without ``0`` that starts and ends with a
    ``1``; a maximal block is a block not included in a larger one. A run of
    ``2``s (``X``) alone is not a block. ``O(mn)``.
    """
    total = 0
    for row in matrix:
        blocks = 0
        in_run = False
        run_has_one = False
        for column in perm:
            value = row[column]
            if value == 0:
                blocks += in_run and run_has_one
                in_run = run_has_one = False
            else:
                in_run = True
                run_has_one = run_has_one or value == 1
        blocks += in_run and run_has_one
        total += blocks
    return int(total)
