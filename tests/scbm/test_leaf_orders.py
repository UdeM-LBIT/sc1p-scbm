import random
from itertools import pairwise, permutations
from pathlib import Path

import pytest

pytest.importorskip("pysat")
pytest.importorskip("sowing")

from scbm.history import compare_histories
from scbm.leaf_orders import pareto_front, solve_weighted
from scbm.score import block_cost
from synteny_tree.leaf_orders import adjacency_rows
from synteny_tree.nhx import EventCosts, read_histories


def exhaustive(matrix, orders, opens, ext):
    n = len(matrix[0])
    leaves = adjacency_rows(n, orders)
    scores = []
    for perm in permutations(range(n)):
        cost = sum(
            w * block_cost([row], list(perm)) + e * row.count(1)
            for row, w, e in zip(matrix, opens, ext)
        )
        broken = block_cost(leaves, list(perm)) - len(leaves)
        scores.append((cost, broken))
    return set(scores)


def nondominated(scores):
    return {
        (c, d)
        for c, d in scores
        if not any(a <= c and b <= d and (a < c or b < d) for a, b in scores)
    }


def test_pareto_and_weighted_match_exhaustive():
    rng = random.Random(1729)
    for _ in range(20):
        matrix = [[rng.randrange(3) for _ in range(5)] for _ in range(4)]
        opens = [rng.randrange(4) for _ in matrix]
        ext = [rng.randrange(3) for _ in matrix]
        orders = [rng.sample(range(5), rng.randrange(2, 6)) for _ in range(2)]
        scores = exhaustive(matrix, orders, opens, ext)
        front = pareto_front(matrix, orders, row_open=opens, row_ext=ext)
        assert {(r.history_cost, r.broken_adjacencies) for r in front} == nondominated(scores)
        for weight in (0, 1, 4):
            result = solve_weighted(matrix, orders, row_open=opens, row_ext=ext, leaf_weight=weight)
            assert result.history_cost + weight * result.broken_adjacencies == min(
                c + weight * d for c, d in scores
            )


def test_empty_rows_leaf_reversal_and_validation():
    assert pareto_front([], [[0, 1, 2]], ncols=3)[0].broken_adjacencies == 0
    assert adjacency_rows(3, [[0, 1, 2]]) == adjacency_rows(3, [[2, 1, 0]])[::-1]
    with pytest.raises(ValueError):
        adjacency_rows(3, [[0, 0]])
    with pytest.raises(ValueError):
        solve_weighted([[1, 0]], row_open=[-1])


def test_directional_leaf_orders_match_exhaustive():
    rng = random.Random(482)
    for _ in range(20):
        matrix = [[rng.randrange(3) for _ in range(5)] for _ in range(3)]
        orders = [rng.sample(range(5), rng.randrange(2, 6)) for _ in range(2)]
        scores = set()
        for permutation in permutations(range(5)):
            broken = 0
            for order in orders:
                projected = [column for column in permutation if column in order]
                actual = set(pairwise(projected))
                broken += sum(pair not in actual for pair in pairwise(order))
            scores.add((block_cost(matrix, list(permutation)), broken))
        front = pareto_front(matrix, orders, allow_reverse=False)
        assert {(r.history_cost, r.broken_adjacencies) for r in front} == nondominated(scores)
        for weight in (0, 1, 5):
            result = solve_weighted(matrix, orders, leaf_weight=weight, allow_reverse=False)
            assert result.history_cost + weight * result.broken_adjacencies == min(
                cost + weight * broken for cost, broken in scores
            )


def test_directional_mode_keeps_reverse_global_order_available():
    result = solve_weighted([[0, 0, 0]], [[2, 1, 0]], allow_reverse=False)
    assert result.permutation == (2, 1, 0)
    assert result.broken_adjacencies == 0
    reverse_is_allowed = solve_weighted([[0, 0]], [[1, 0]])
    assert reverse_is_allowed.broken_adjacencies == 0


def test_crispr_nhx_costs():
    path = (
        Path(__file__).resolve().parents[2]
        / "examples/crispr-class1/crispr-class1-out-lo20-le10-go1.out.nhx"
    )
    (history,) = read_histories(path)
    costs = EventCosts(loss_open=20, loss_ext=10, gain_open=1)
    assert history.input_cost == history.inout_cost(costs) == 613
    (result,) = compare_histories([history], costs)
    assert (result.history_cost, result.block_count, result.broken_adjacencies) == (653, 19, 0)


def test_multiple_nhx_records_and_leaf_content_validation(tmp_path):
    path = (
        Path(__file__).resolve().parents[2]
        / "examples/crispr-class1/crispr-class1-out-lo20-le10-go1.out.nhx"
    )
    record = path.read_text().splitlines()[-1]
    target = tmp_path / "solutions.nhx"
    target.write_text(
        f"# count=2\n# solution no. 1, cost=613.0\n{record}\n"
        f"# solution no. 2, cost=613.0\n{record}\n"
    )
    histories = read_histories(target)
    assert len(histories) == 2
    result = compare_histories(histories, EventCosts(20, 10, 1))
    assert {r.history for r in result} == {"1", "2"}
    with pytest.raises(ValueError, match="exactly its families"):
        histories[0].leaf_columns({"I-C1": ["1", "2"]})
    with pytest.raises(ValueError, match="not a leaf"):
        histories[0].leaf_columns({"Class1": []})
