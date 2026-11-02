"""SCBM meets the event-matrix lower bound ``λ + γ`` exactly when ``M`` has SC1P.

One exact SCBM solve therefore also answers the DEMOSH decision problem of the
paper: ``has_sc1p`` iff the optimum equals the lower bound, equivalently iff
``Φ(M)`` is satisfiable.
"""

from __future__ import annotations

from scbm.score import block_lower_bound
from scbm.types import AnalysisReport, Matrix


def analyze(matrix: Matrix, *, solver: str = "auto") -> AnalysisReport:
    from scbm import solve

    result = solve(matrix, solver=solver)
    return AnalysisReport(
        has_sc1p=result.cost == block_lower_bound(matrix),
        permutation=result.permutation,
        cost=result.cost,
    )
