"""Reference SCBM solver: score all ``n!`` orders. Practical up to ``n`` of about 9."""

from __future__ import annotations

import itertools

from sc1p import validate_ternary
from scbm import register
from scbm.score import block_cost
from scbm.types import Matrix, OptimizeResult, Permutation


@register("brute_force")
class BruteForceSolver:
    def solve(self, matrix: Matrix) -> OptimizeResult:
        _, n = validate_ternary(matrix)
        best_perm = list(range(n))
        best_cost = block_cost(matrix, best_perm)
        for perm in itertools.permutations(range(n)):
            if best_cost == 0:
                break
            cost = block_cost(matrix, list(perm))
            if cost < best_cost:
                best_cost, best_perm = cost, list(perm)
        return OptimizeResult(best_perm, best_cost)

    def solve_all(self, matrix: Matrix) -> list[Permutation]:
        _, n = validate_ternary(matrix)
        best = self.solve(matrix).cost
        return [
            list(perm)
            for perm in itertools.permutations(range(n))
            if block_cost(matrix, list(perm)) == best
        ]
