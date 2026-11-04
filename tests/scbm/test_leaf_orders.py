import random
from itertools import pairwise, permutations
from pathlib import Path

import pytest

pytest.importorskip("pysat")
pytest.importorskip("sowing")

from scbm.history import compare_histories
from scbm.leaf_orders import (
    extension_pareto_front,
    extension_rows,
    pareto_front,
    solve_weighted,
    solve_weighted_all,
)
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


def test_extension_pair_losses_and_exact_pareto():
    # One loss for each observed pair AB, BC and CD.
    orders = [[0, 1, 2, 3]]
    rows = extension_rows(5, orders)
    assert rows == [[1, 1, 0, 0, 2], [0, 1, 1, 0, 2], [0, 0, 1, 1, 2]]
    assert block_cost([rows[1]], [1, 0, 2, 3, 4]) == 2
    matrix = [[1, 0, 1, 0, 2], [0, 1, 0, 1, 1]]
    for loss_open, loss_ext in ((3, 2), (0, 2), (2, 0)):
        scores = {}
        for perm in permutations(range(5)):
            if perm.index(0) > perm.index(1):
                continue
            history_cost = block_cost(matrix, list(perm))
            extension_cost = loss_open * block_cost(rows, list(perm)) + loss_ext * sum(
                row.count(1) for row in rows
            )
            scores[perm] = (history_cost, extension_cost)
        front = nondominated(set(scores.values()))
        found = extension_pareto_front(
            matrix, orders, loss_open=loss_open, loss_ext=loss_ext, all_optima=True
        )
        assert {r.permutation for r in found} == {
            p for p, score in scores.items() if score in front
        }
        assert all((r.history_cost, r.extension_cost) == scores[r.permutation] for r in found)


def test_extension_short_leaves():
    assert extension_rows(3, [[], [0]]) == []
    assert extension_rows(3, [[0, 1]]) == [[1, 1, 2]]
    with pytest.raises(ValueError):
        extension_rows(3, [[0, 0]])


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
    assert list(result.permutation) == [2, 1, 0]
    assert result.broken_adjacencies == 0
    reverse_is_allowed = solve_weighted([[0, 0]], [[1, 0]])
    assert reverse_is_allowed.broken_adjacencies == 0


def test_all_optima_matches_exhaustive():
    rng = random.Random(2024)
    for _ in range(10):
        matrix = [[rng.randrange(3) for _ in range(5)] for _ in range(4)]
        opens = [rng.randrange(4) for _ in matrix]
        ext = [rng.randrange(3) for _ in matrix]
        orders = [rng.sample(range(5), rng.randrange(2, 6)) for _ in range(2)]
        leaves = adjacency_rows(5, orders)
        scores = {}
        for permutation in permutations(range(5)):
            if permutation.index(0) > permutation.index(1):
                continue
            cost = sum(
                w * block_cost([row], list(permutation)) + e * row.count(1)
                for row, w, e in zip(matrix, opens, ext)
            )
            broken = block_cost(leaves, list(permutation)) - len(leaves)
            scores[permutation] = (cost, broken)
        front = nondominated(set(scores.values()))
        found = pareto_front(matrix, orders, row_open=opens, row_ext=ext, all_optima=True)
        assert {r.permutation for r in found} == {
            permutation for permutation, score in scores.items() if score in front
        }
        for weight in (0, 1, 4):
            best = min(cost + weight * broken for cost, broken in scores.values())
            found = solve_weighted_all(
                matrix, orders, row_open=opens, row_ext=ext, leaf_weight=weight
            )
            assert {r.permutation for r in found} == {
                permutation
                for permutation, (cost, broken) in scores.items()
                if cost + weight * broken == best
            }


def test_crispr_nhx_costs():
    path = (
        Path(__file__).resolve().parents[2]
        / "examples/crispr-class1/crispr-class1-out-lo20-le10-go1.out.nhx"
    )
    (history,) = read_histories(path)
    costs = EventCosts(loss_open=20, loss_ext=10, gain_open=1)
    assert history.input_cost == history.inout_cost(costs) == 574
    (result,) = compare_histories([history], costs)
    assert result.history_cost == 574
    assert result.block_count == 18
    assert result.broken_adjacencies == 0


def test_multiple_nhx_records_and_leaf_content_validation(tmp_path):
    path = (
        Path(__file__).resolve().parents[2]
        / "examples/crispr-class1/crispr-class1-out-lo20-le10-go1.out.nhx"
    )
    record = path.read_text().splitlines()[-1]
    target = tmp_path / "solutions.nhx"
    target.write_text(
        f"# count=2\n# solution no. 1, cost=574.0\n{record}\n"
        f"# solution no. 2, cost=574.0\n{record}\n"
    )
    histories = read_histories(target)
    assert len(histories) == 2
    result = compare_histories(histories, EventCosts(20, 10, 1))
    assert {r.history for r in result} == {"1", "2"}
    with pytest.raises(ValueError, match="exactly its families"):
        histories[0].leaf_columns({"I-C1": ["1", "2"]})
    with pytest.raises(ValueError, match="not a leaf"):
        histories[0].leaf_columns({"Class1": []})
