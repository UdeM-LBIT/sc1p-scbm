"""Tests for SC1P decision and enumeration across all installed backends."""

from __future__ import annotations

import random
from math import comb

import pytest

import sc1p


def test_solve_satisfiable(sc1p_solver, paper_matrix):
    result = sc1p.solve(paper_matrix, solver=sc1p_solver)
    assert result.satisfiable
    assert result.permutation is not None
    assert sc1p.verify(paper_matrix, result.permutation)


def test_solve_unsatisfiable(sc1p_solver, unsatisfiable_matrix):
    result = sc1p.solve(unsatisfiable_matrix, solver=sc1p_solver)
    assert not result.satisfiable
    assert result.permutation is None


def test_solve_result_unpacks(sc1p_solver, satisfiable_matrix):
    ok, perm = sc1p.solve(satisfiable_matrix, solver=sc1p_solver)
    assert ok and perm is not None
    assert sc1p.verify(satisfiable_matrix, perm)


def test_solve_all_matches_brute_force(sc1p_solver, paper_matrix):
    expected = {tuple(p) for p in sc1p.solve_all(paper_matrix, solver="brute_force")}
    got = {tuple(p) for p in sc1p.solve_all(paper_matrix, solver=sc1p_solver)}
    assert got == expected


def test_paper_example_has_twelve_solutions(paper_matrix):
    perms = sc1p.solve_all(paper_matrix, solver="brute_force")
    assert len(perms) == 12


def test_auto_selects_a_backend(satisfiable_matrix):
    result = sc1p.solve(satisfiable_matrix, solver="auto")
    assert result.satisfiable


def test_unknown_solver_raises(satisfiable_matrix):
    import pytest

    with pytest.raises(ValueError):
        sc1p.solve(satisfiable_matrix, solver="does_not_exist")


def test_custom_backend_registration():
    from sc1p.solvers import get, register
    from sc1p.types import SolveResult

    @register("dummy_identity")
    class _Dummy:
        def solve(self, matrix):
            n = len(matrix[0]) if matrix else 0
            return SolveResult(True, list(range(n)))

        def solve_all(self, matrix):
            n = len(matrix[0]) if matrix else 0
            return [list(range(n))]

    solver = get("dummy_identity")
    assert solver.solve([[2, 2]]).permutation == [0, 1]


@pytest.mark.parametrize("seed", range(50))
def test_formula_size_matches_the_supplement(seed):
    pytest.importorskip("pysat")
    from sc1p.solvers.sat import build_phi

    rng = random.Random(seed)
    n, m = rng.randint(2, 8), rng.randint(1, 8)
    matrix = [[rng.choice([0, 1, 2]) for _ in range(n)] for _ in range(m)]
    agreements = 0
    distinct = set()
    for row in matrix:
        ones = [j for j in range(n) if row[j] == 1]
        if len(ones) >= 2:
            zeros = [j for j in range(n) if row[j] == 0]
            agreements += len(zeros) * (len(ones) - 1)
            distinct |= {(z, ones[0], j) for z in zeros for j in ones[1:]}
    cnf = build_phi(matrix, n, symmetry_break=True)
    assert len(cnf.clauses) == 2 * comb(n, 3) + 2 * len(distinct) + 1
    assert len(cnf.clauses) <= 2 * comb(n, 3) + 2 * agreements + 1
    assert len(set(map(tuple, cnf.clauses))) == len(cnf.clauses)
