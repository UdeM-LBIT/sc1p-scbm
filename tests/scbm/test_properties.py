"""Property-based checks of the SCBM solver contract."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import scbm
from scbm.score import block_cost

ternary_matrices = st.tuples(
    st.integers(min_value=1, max_value=5),
    st.integers(min_value=1, max_value=5),
).flatmap(
    lambda shape: st.lists(
        st.lists(st.integers(min_value=0, max_value=2), min_size=shape[1], max_size=shape[1]),
        min_size=shape[0],
        max_size=shape[0],
    )
)


@settings(max_examples=50, deadline=None)
@given(ternary_matrices)
def test_brute_force_returns_valid_permutation_and_cost(matrix):
    result = scbm.solve(matrix, solver="brute_force")
    assert sorted(result.permutation) == list(range(len(matrix[0])))
    assert block_cost(matrix, result.permutation) == result.cost


@settings(max_examples=50, deadline=None)
@given(ternary_matrices)
def test_block_cost_is_reversal_invariant(matrix):
    perm = list(range(len(matrix[0])))
    assert block_cost(matrix, perm) == block_cost(matrix, perm[::-1])


@settings(max_examples=40, deadline=None)
@given(ternary_matrices)
def test_maxsat_matches_brute_force(matrix):
    if "maxsat" not in scbm.available():
        pytest.skip("needs pip install 'scbm[sat]'")
    result = scbm.solve(matrix, solver="maxsat")
    assert result.cost == scbm.solve(matrix, solver="brute_force").cost
    assert block_cost(matrix, result.permutation) == result.cost


@pytest.mark.parametrize(
    "matrix",
    [
        [[0]],
        [[1]],
        [[2]],
        [[0, 0, 0]],
        [[1, 1, 1]],
        [[2, 2, 2]],
        [[1, 0, 1], [1, 0, 1]],
        [[0, 1, 0], [0, 1, 0]],
    ],
)
def test_degenerate_and_symmetric_instances(matrix):
    result = scbm.solve(matrix, solver="brute_force")
    assert sorted(result.permutation) == list(range(len(matrix[0])))
    assert block_cost(matrix, result.permutation) == result.cost
