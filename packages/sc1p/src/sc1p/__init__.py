"""SC1P — Sandwich Consecutive Ones Property of ternary matrices.

A matrix ``M ∈ {0, 1, X}^{m×n}`` (stored with ``X = 2``) has SC1P iff some
column order ``π`` leaves no ``0`` strictly between two ``1``-entries of a row,
once the row's ``X``-entries are deleted.
"""

from __future__ import annotations

__version__ = "0.1.0"

from sc1p.matrices import random_matrix, sc1p_example
from sc1p.solvers import available, get, register
from sc1p.ternary import validate_ternary
from sc1p.types import Matrix, Permutation, SolveResult
from sc1p.verify import verify

__all__ = [
    "Matrix",
    "Permutation",
    "SolveResult",
    "__version__",
    "available",
    "get",
    "random_matrix",
    "register",
    "sc1p_example",
    "solve",
    "solve_all",
    "validate_ternary",
    "verify",
]


def solve(matrix: Matrix, *, solver: str = "auto") -> SolveResult:
    return get(solver).solve(matrix)


def solve_all(matrix: Matrix, *, solver: str = "auto") -> list[Permutation]:
    """Every SC1P column order, enumerated by the selected backend.

    The SAT backend blocks each satisfying pair assignment and repeats; the
    brute-force backend scans all ``n!`` orders.
    """
    return get(solver).solve_all(matrix)
