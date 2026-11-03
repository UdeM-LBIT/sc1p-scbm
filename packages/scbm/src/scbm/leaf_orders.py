"""Exact weighted SCBM and leaf-adjacency trade-offs.

Leaf orders are sequences of column indices, not signed gene orders. Reversal
is allowed by default. The returned Pareto front contains one representative
order for every nondominated (history cost, broken adjacencies) pair.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from sc1p import validate_ternary
from scbm.score import block_cost
from scbm.types import Matrix


@dataclass(frozen=True)
class LeafResult:
    permutation: tuple[int, ...]
    history_cost: int
    broken_adjacencies: int
    block_count: int


def _prepare(
    matrix: Matrix,
    leaf_orders: Sequence[Sequence[int]],
    row_open: Sequence[int] | None,
    row_ext: Sequence[int] | None,
    ncols: int | None,
):
    _, n = validate_ternary(matrix)
    if not matrix and ncols is not None:
        n = ncols
    if ncols is not None and (ncols < 0 or ncols != n):
        raise ValueError("ncols must match the matrix width")
    opens = list(row_open) if row_open is not None else [1] * len(matrix)
    extensions = list(row_ext) if row_ext is not None else [0] * len(matrix)
    for values in (opens, extensions):
        if len(values) != len(matrix) or any(
            not isinstance(x, int) or isinstance(x, bool) or x < 0 for x in values
        ):
            raise ValueError("row weights must be non-negative integers, one per matrix row")
    rows: Matrix = []
    if leaf_orders:
        from synteny_tree.leaf_orders import adjacency_rows

        rows = adjacency_rows(n, leaf_orders)
    return n, opens, extensions, rows


def _solve(
    matrix: Matrix,
    n: int,
    opens: list[int],
    extensions: list[int],
    leaf_rows: Matrix,
    *,
    leaf_orders: Sequence[Sequence[int]],
    allow_reverse: bool,
    leaf_limit: int | None = None,
    leaf_weight: int = 0,
) -> LeafResult | None:
    from pysat.card import CardEnc, EncType
    from pysat.examples.rc2 import RC2

    from sc1p.encoding.sat import extract_perm, num_pairs, transitivity_triples
    from scbm.exact.maxsat import _add_row, _before, _Builder

    builder = _Builder(num_pairs(n))
    for ab, bc, ac in transitivity_triples(n):
        builder.hard([-(ab + 1), -(bc + 1), ac + 1])
        builder.hard([ab + 1, bc + 1, -(ac + 1)])
    if n >= 2 and (allow_reverse or not leaf_rows):
        builder.hard([_before(0, 1, n)])

    leaf_starts: list[int] = []
    active_leaves = 0
    row_specs = [(r, w, False) for r, w in zip(matrix, opens)]
    if allow_reverse:
        row_specs += [(r, leaf_weight, True) for r in leaf_rows]
    for row, weight, is_leaf in row_specs:
        ones = [j for j, x in enumerate(row) if x == 1]
        zeros = [j for j, x in enumerate(row) if x == 0]
        if len(ones) <= 1 or not zeros:
            continue
        old_soft = len(builder.wcnf.soft)
        old_topw = builder.wcnf.topw
        _add_row(builder, n, ones, zeros)
        new_soft = builder.wcnf.soft[old_soft:]
        if is_leaf:
            active_leaves += 1
            leaf_starts.extend(-clause[0] for clause in new_soft)
        # _add_row appends unit weights; remove them and add desired weights.
        del builder.wcnf.soft[old_soft:]
        del builder.wcnf.wght[old_soft:]
        builder.wcnf.topw = old_topw
        for clause in new_soft:
            if weight:
                builder.soft(clause, weight)

    if not allow_reverse:
        for order in leaf_orders:
            for left, right in pairwise(order):
                between = []
                for other in order:
                    if other in (left, right):
                        continue
                    indicator = builder.var()
                    before_left = _before(left, other, n)
                    before_right = _before(other, right, n)
                    builder.hard([-indicator, before_left])
                    builder.hard([-indicator, before_right])
                    builder.hard([indicator, -before_left, -before_right])
                    between.append(indicator)
                # broken iff right is not immediately after left on this leaf.
                broken = builder.var()
                direction = _before(left, right, n)
                builder.hard([-broken, -direction, *between])
                builder.hard([broken, direction])
                for indicator in between:
                    builder.hard([broken, -indicator])
                leaf_starts.append(broken)
                if leaf_weight:
                    builder.soft([-broken], leaf_weight)

    if leaf_limit is not None:
        limit = active_leaves + leaf_limit
        if limit < len(leaf_starts):
            card = CardEnc.atmost(
                lits=leaf_starts, bound=limit, top_id=builder.top, encoding=EncType.seqcounter
            )
            for clause in card.clauses:
                builder.hard(clause)
            builder.top = card.nv
    if n <= 1:
        perm = list(range(n))
    else:
        with RC2(builder.wcnf) as rc2:
            model = rc2.compute()
        if model is None:
            return None
        truth = {abs(value): value > 0 for value in model}
        perm = extract_perm(truth, n, one_indexed=True)
    blocks = block_cost(matrix, perm)
    history_cost = sum(
        w * block_cost([r], perm) + e * r.count(1) for r, w, e in zip(matrix, opens, extensions)
    )
    if allow_reverse:
        broken = block_cost(leaf_rows, perm) - len(leaf_rows)
    else:
        broken = 0
        for order in leaf_orders:
            content = set(order)
            projected = [column for column in perm if column in content]
            adjacencies = set(pairwise(projected))
            broken += sum(pair not in adjacencies for pair in pairwise(order))
    return LeafResult(tuple(perm), history_cost, broken, blocks)


def solve_weighted(
    matrix: Matrix,
    leaf_orders: Sequence[Sequence[int]] = (),
    *,
    row_open: Sequence[int] | None = None,
    row_ext: Sequence[int] | None = None,
    leaf_weight: int = 1,
    ncols: int | None = None,
    allow_reverse: bool = True,
) -> LeafResult:
    """Minimize weighted history cost plus ``leaf_weight`` per broken adjacency.

    Row costs are ``row_open[i] * blocks + row_ext[i] * number_of_ones``.
    By default, unsigned leaf orders match up to reversal. If ``allow_reverse``
    is false, an adjacency is respected only in the observed direction.
    """
    if not isinstance(leaf_weight, int) or isinstance(leaf_weight, bool) or leaf_weight < 0:
        raise ValueError("leaf_weight must be a non-negative integer")
    n, opens, extensions, rows = _prepare(matrix, leaf_orders, row_open, row_ext, ncols)
    result = _solve(
        matrix,
        n,
        opens,
        extensions,
        rows,
        leaf_orders=leaf_orders,
        allow_reverse=allow_reverse,
        leaf_weight=leaf_weight,
    )
    if result is None:
        raise RuntimeError("weighted MaxSAT instance is unexpectedly unsatisfiable")
    return result


def pareto_front(
    matrix: Matrix,
    leaf_orders: Sequence[Sequence[int]] = (),
    *,
    row_open: Sequence[int] | None = None,
    row_ext: Sequence[int] | None = None,
    ncols: int | None = None,
    allow_reverse: bool = True,
) -> list[LeafResult]:
    """Return every nondominated cost pair, one order per pair, using exact bounds."""
    n, opens, extensions, rows = _prepare(matrix, leaf_orders, row_open, row_ext, ncols)
    front: list[LeafResult] = []
    best_cost: int | None = None
    for bound in range(len(rows) + 1):
        result = _solve(
            matrix,
            n,
            opens,
            extensions,
            rows,
            leaf_orders=leaf_orders,
            allow_reverse=allow_reverse,
            leaf_limit=bound,
        )
        if result is not None and (best_cost is None or result.history_cost < best_cost):
            front.append(result)
            best_cost = result.history_cost
    return front
