"""The precedence MaxSAT encoding (Algorithm S2 of the supplement) is exact."""

from __future__ import annotations

import random

import pytest

import sc1p
import scbm
from _matrices import CROSS_CHECK_MATRICES
from scbm.score import block_cost

pytestmark = pytest.mark.skipif(
    "maxsat" not in scbm.available(),
    reason="needs pip install 'scbm[sat]'",
)


@pytest.mark.parametrize("matrix", CROSS_CHECK_MATRICES)
def test_matches_brute_force(matrix):
    result = scbm.solve(matrix, solver="maxsat")
    assert result.cost == scbm.solve(matrix, solver="brute_force").cost
    assert block_cost(matrix, result.permutation) == result.cost
    assert sorted(result.permutation) == list(range(len(matrix[0])))


def test_raw_rc2_optimum_is_total_block_cost(monkeypatch):
    from pysat.examples.rc2 import RC2

    matrix = [
        [1, 0, 1],
        [0, 1, 1],
        [1, 1, 0],
        [1, 0, 1],  # Duplicate active row.
        [0, 1, 2],  # One block under every order: a single 1.
        [1, 2, 1],  # One block under every order: no 0.
        [2, 0, 2],
        [0, 0, 0],
        [2, 2, 2],
    ]
    raw_costs = []
    compute = RC2.compute

    def compute_and_record(self, *args, **kwargs):
        model = compute(self, *args, **kwargs)
        raw_costs.append(self.cost)
        return model

    monkeypatch.setattr(RC2, "compute", compute_and_record)
    expected = scbm.solve(matrix, solver="brute_force").cost
    assert expected == 7
    result = scbm.solve(matrix, solver="maxsat")
    assert result.cost == block_cost(matrix, result.permutation) == expected
    assert raw_costs
    assert all(cost == expected for cost in raw_costs)


def test_random_matrices_match_brute_force():
    rng = random.Random(20260721)
    for _ in range(300):
        n = rng.randint(2, 5)
        matrix = sc1p.random_matrix(rng.randint(1, 2 * n), n, p1=0.3, p0=0.5, rng=rng)
        expected = scbm.solve(matrix, solver="brute_force").cost
        assert scbm.solve(matrix, solver="maxsat").cost == expected, matrix


def test_six_to_eight_columns():
    rng = random.Random(20260828)
    for _ in range(40):
        n = rng.randint(6, 8)
        matrix = sc1p.random_matrix(rng.randint(3, 2 * n), n, p1=0.35, p0=0.35, rng=rng)
        expected = scbm.solve(matrix, solver="brute_force").cost
        assert scbm.solve(matrix, solver="maxsat").cost == expected, matrix


@pytest.mark.parametrize("matrix", CROSS_CHECK_MATRICES + [[[2, 0, 2]], [[0, 0, 0]]])
def test_solve_all_matches_brute_force(matrix):
    expected = {tuple(perm) for perm in scbm.solve_all(matrix, solver="brute_force")}
    got = {tuple(perm) for perm in scbm.solve_all(matrix, solver="maxsat")}
    assert got == expected


def test_solve_all_random_matches_brute_force():
    rng = random.Random(20261101)
    for _ in range(40):
        n = rng.randint(2, 5)
        matrix = sc1p.random_matrix(rng.randint(1, 2 * n), n, p1=0.3, p0=0.5, rng=rng)
        expected = {tuple(perm) for perm in scbm.solve_all(matrix, solver="brute_force")}
        got = {tuple(perm) for perm in scbm.solve_all(matrix, solver="maxsat")}
        assert got == expected, matrix


@pytest.mark.parametrize("seed", range(50))
def test_formula_size_matches_the_supplement(seed):
    from math import comb

    from scbm.exact.maxsat import build_psi

    rng = random.Random(seed)
    n, m = rng.randint(2, 7), rng.randint(1, 7)
    matrix = [[rng.choice([0, 1, 2]) for _ in range(n)] for _ in range(m)]
    rows = [
        ([j for j in range(n) if row[j] == 1], [j for j in range(n) if row[j] == 0])
        for row in matrix
    ]
    active = [(ones, zeros) for ones, zeros in rows if len(ones) >= 2 and zeros]
    delta = int(any(ones and (len(ones) == 1 or not zeros) for ones, zeros in rows))
    wcnf, _ = build_psi(matrix, n)
    if wcnf is None:
        return
    variables = comb(n, 2) + delta
    hard = 2 * comb(n, 3) + 1 + delta
    for ones, zeros in active:
        k1, k0 = len(ones), len(zeros)
        variables += k1 * (k1 - 1) * (k1 + k0 - 1) + k1
        hard += k1 * (k1 - 1) * (4 * (k1 + k0 - 2) + 2) + k1**2
    assert wcnf.nv == variables
    assert len(wcnf.hard) == hard
    assert len(wcnf.soft) == sum(len(ones) for ones, _ in active) + delta
