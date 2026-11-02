from __future__ import annotations

from typing import NamedTuple

#: Ternary matrix as a list of rows: ``0`` for a family kept in the event,
#: ``1`` for a family lost or gained in the event, ``2`` for ``X`` (a family
#: absent from the event context).
Matrix = list[list[int]]

#: Column order: ``perm[k]`` is the column placed at position ``k``.
Permutation = list[int]


class SolveResult(NamedTuple):
    satisfiable: bool
    permutation: Permutation | None
