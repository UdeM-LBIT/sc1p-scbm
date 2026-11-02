"""Result types of the SCBM solvers."""

from __future__ import annotations

from typing import NamedTuple

from sc1p.types import Matrix, Permutation

__all__ = ["AnalysisReport", "Matrix", "OptimizeResult", "Permutation"]


class OptimizeResult(NamedTuple):
    permutation: Permutation
    cost: int


class AnalysisReport(NamedTuple):
    has_sc1p: bool
    permutation: Permutation
    cost: int
