"""Reference SC1P solver: test all ``n!`` orders. Practical up to ``n`` of about 10."""

from __future__ import annotations

import itertools

from sc1p.solvers import register
from sc1p.ternary import validate_ternary
from sc1p.types import Matrix, Permutation, SolveResult
from sc1p.verify import verify


@register("brute_force")
class BruteForceSolver:
    def solve(self, matrix: Matrix) -> SolveResult:
        _, n = validate_ternary(matrix)
        for perm in itertools.permutations(range(n)):
            if verify(matrix, list(perm)):
                return SolveResult(True, list(perm))
        return SolveResult(False, None)

    def solve_all(self, matrix: Matrix) -> list[Permutation]:
        _, n = validate_ternary(matrix)
        return [list(p) for p in itertools.permutations(range(n)) if verify(matrix, list(p))]
