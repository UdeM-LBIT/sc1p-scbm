"""SCBM — Sandwich Consecutive-Block Minimization on ternary matrices.

For a column order ``π`` of ``M ∈ {0, 1, X}^{m×n}``, ``b(M^π)`` counts the
maximal blocks of all rows, and ``SCBM(M) = min_π b(M^π)``. A block is a
substring without ``0`` that starts and ends with a ``1``.
"""

from __future__ import annotations

__version__ = "0.1.0"

from sc1p import validate_ternary
from sc1p.registry import SolverRegistry
from scbm.analyze import analyze
from scbm.score import block_cost
from scbm.types import Matrix, OptimizeResult, Permutation

registry: SolverRegistry = SolverRegistry(
    package="scbm",
    backend_modules={
        "brute_force": "scbm.exact.brute_force",
        "maxsat": "scbm.exact.maxsat",
    },
    auto_order=("maxsat", "brute_force"),
    extra_map={"maxsat": "sat"},
)

register = registry.register
get = registry.get
available = registry.available

__all__ = [
    "Matrix",
    "OptimizeResult",
    "Permutation",
    "__version__",
    "analyze",
    "available",
    "block_cost",
    "get",
    "register",
    "solve",
    "solve_all",
    "validate_ternary",
]


def solve(matrix: Matrix, *, solver: str = "auto") -> OptimizeResult:
    return get(solver).solve(matrix)


def solve_all(matrix: Matrix, *, solver: str = "auto") -> list[Permutation]:
    """Every permutation reaching the optimum found by *solver*.

    Exact backends with model enumeration (SAT and MaxSAT) block each optimal
    assignment instead of scanning all ``n!`` orders. Brute force and custom
    backends without ``solve_all`` fall back to an ``n!`` scan.
    """
    from itertools import permutations

    _, n = validate_ternary(matrix)
    implementation = get(solver)
    if hasattr(implementation, "solve_all"):
        return implementation.solve_all(matrix)
    if n <= 1:
        return [list(range(n))]
    best = implementation.solve(matrix).cost
    return [
        list(perm)
        for perm in permutations(range(n))
        if block_cost(matrix, list(perm)) == best
    ]
