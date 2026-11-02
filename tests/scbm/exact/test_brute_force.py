"""Exact SCBM backends agree with brute force."""

from __future__ import annotations

import pytest

import sc1p
import scbm
from _matrices import CROSS_CHECK_MATRICES, random_matrices
from scbm import analyze
from scbm.score import block_cost, block_lower_bound


def test_min_cost_on_paper_matrix(scbm_solver, paper_matrix):
    result = scbm.solve(paper_matrix, solver=scbm_solver)
    assert result.cost == block_lower_bound(paper_matrix)
    assert sc1p.verify(paper_matrix, result.permutation)


def test_result_unpacks(scbm_solver, satisfiable_matrix):
    perm, cost = scbm.solve(satisfiable_matrix, solver=scbm_solver)
    assert cost == block_lower_bound(satisfiable_matrix)
    assert block_cost(satisfiable_matrix, perm) == cost


def test_unsatisfiable_exceeds_lower_bound(unsatisfiable_matrix):
    assert (
        scbm.solve(unsatisfiable_matrix, solver="brute_force").cost
        > block_lower_bound(unsatisfiable_matrix)
    )


def test_lower_bound_iff_sc1p(unsatisfiable_matrix, satisfiable_matrix):
    for matrix in (satisfiable_matrix, unsatisfiable_matrix):
        assert (
            scbm.solve(matrix, solver="brute_force").cost == block_lower_bound(matrix)
        ) == sc1p.solve(matrix, solver="brute_force").satisfiable


def test_solve_all_returns_optimal_perms(satisfiable_matrix):
    solutions = scbm.solve_all(satisfiable_matrix, solver="brute_force")
    assert solutions
    assert all(
        block_cost(satisfiable_matrix, perm) == block_lower_bound(satisfiable_matrix)
        for perm in solutions
    )


@pytest.mark.parametrize("matrix", CROSS_CHECK_MATRICES + random_matrices())
def test_backend_matches_brute_force_optimum(scbm_solver, matrix):
    reference = scbm.solve(matrix, solver="brute_force").cost
    result = scbm.solve(matrix, solver=scbm_solver)
    assert result.cost == reference
    assert block_cost(matrix, result.permutation) == result.cost


def test_twos_join_ones_into_one_block():
    matrix = [[1, 2, 0, 1, 0], [0, 1, 2, 0, 1]]
    assert scbm.solve(matrix, solver="brute_force").cost == block_lower_bound(matrix)


def test_analyze_sc1p(paper_matrix):
    report = analyze(paper_matrix)
    assert report.has_sc1p
    assert report.cost == block_lower_bound(paper_matrix)
    assert sc1p.verify(paper_matrix, report.permutation)


def test_analyze_not_sc1p(unsatisfiable_matrix):
    report = analyze(unsatisfiable_matrix)
    assert not report.has_sc1p
    assert report.cost > block_lower_bound(unsatisfiable_matrix)
    assert block_cost(unsatisfiable_matrix, report.permutation) == report.cost


def test_analyze_report_unpacks(satisfiable_matrix):
    has_sc1p, _, cost = analyze(satisfiable_matrix)
    assert has_sc1p and cost == block_lower_bound(satisfiable_matrix)
