"""Compare InOutParsimony histories under the SCBM objective.

The NHX records and their event matrices come from :mod:`synteny_tree.nhx`;
this module only searches column orders, optionally trading history cost
against broken observed leaf adjacencies.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from scbm.leaf_orders import (
    LeafResult,
    extension_pareto_front,
    pareto_front,
    solve_weighted,
    solve_weighted_all,
)
from synteny_tree.nhx import EventCosts, HistoryInstance


@dataclass(frozen=True)
class CandidateResult:
    history: str
    inout_cost: float | None
    order: tuple[str, ...]
    history_cost: int
    broken_adjacencies: int
    block_count: int
    solutions: int | None = None
    extension_cost: int | None = None
    total_cost: int | None = None


def _first_per_pair(
    results: Sequence[LeafResult], criterion: str = "adjacency"
) -> list[LeafResult]:
    seen = set()
    unique = []
    for result in results:
        key = (
            result.history_cost,
            result.extension_cost if criterion == "extension" else result.broken_adjacencies,
        )
        if key not in seen:
            seen.add(key)
            unique.append(result)
    return unique


def compare_histories(
    histories: Sequence[HistoryInstance],
    costs: EventCosts,
    orders: Mapping[str, Sequence[str]] | None = None,
    *,
    mode: str = "pareto",
    leaf_weight: int = 1,
    allow_reverse: bool = True,
    enumerate_all: bool = False,
    leaf_criterion: str = "adjacency",
    progress: Callable[[int, int, str], None] | None = None,
) -> list[CandidateResult]:
    """Compare candidate histories; Pareto uses history cost and leaf disagreement.

    Each Pareto pair reports ``solutions``, the number of orders attaining it,
    up to reversal when reversal is equivalent.
    With *enumerate_all*, every one of those orders is returned instead of one
    representative per pair. In weighted mode, counts are available only when
    *enumerate_all* is enabled; otherwise ``solutions`` is ``None``.
    """
    if mode not in {"pareto", "weighted"}:
        raise ValueError("mode must be 'pareto' or 'weighted'")
    if leaf_criterion not in {"adjacency", "extension"}:
        raise ValueError("leaf_criterion must be 'adjacency' or 'extension'")
    if leaf_criterion == "extension" and (mode != "pareto" or not allow_reverse):
        raise ValueError("extension criterion requires Pareto mode and allows leaf reversal")
    output = []
    for index, history in enumerate(histories, 1):
        if progress is not None:
            progress(index, len(histories), history.name)
        leaves = history.leaf_columns(orders or {})
        opens, ext = history.row_costs(costs)
        kwargs = {
            "row_open": opens,
            "row_ext": ext,
            "ncols": len(history.families),
            "allow_reverse": allow_reverse,
        }
        if mode == "pareto":
            if leaf_criterion == "extension":
                extension_kwargs = {k: v for k, v in kwargs.items() if k != "allow_reverse"}
                found = extension_pareto_front(
                    history.matrix,
                    leaves,
                    all_optima=True,
                    loss_open=costs.loss_open,
                    loss_ext=costs.loss_ext,
                    **extension_kwargs,
                )
            else:
                found = pareto_front(history.matrix, leaves, all_optima=True, **kwargs)
            key = lambda r: (
                r.history_cost,
                r.extension_cost if leaf_criterion == "extension" else r.broken_adjacencies,
            )
            counts = Counter(key(r) for r in found)
            if not enumerate_all:
                found = _first_per_pair(found, leaf_criterion)
            numbers = [counts[key(r)] for r in found]
        elif enumerate_all:
            found = solve_weighted_all(history.matrix, leaves, leaf_weight=leaf_weight, **kwargs)
            counts = Counter((r.history_cost, r.broken_adjacencies) for r in found)
            numbers = [counts[(r.history_cost, r.broken_adjacencies)] for r in found]
        else:
            found = [solve_weighted(history.matrix, leaves, leaf_weight=leaf_weight, **kwargs)]
            numbers = [None]
        for result, count in zip(found, numbers):
            output.append(
                CandidateResult(
                    history.name,
                    history.input_cost,
                    tuple(history.families[i] for i in result.permutation),
                    result.history_cost,
                    result.broken_adjacencies,
                    result.block_count,
                    count,
                    result.extension_cost,
                    result.history_cost + result.extension_cost
                    if result.extension_cost is not None
                    else None,
                )
            )
    if mode == "weighted":
        if not output:
            return []
        best = min(r.history_cost + leaf_weight * r.broken_adjacencies for r in output)
        return [r for r in output if r.history_cost + leaf_weight * r.broken_adjacencies == best]

    def second(r):
        return r.extension_cost if leaf_criterion == "extension" else r.broken_adjacencies

    return [
        r
        for r in output
        if not any(
            s.history_cost <= r.history_cost
            and second(s) <= second(r)
            and (s.history_cost < r.history_cost or second(s) < second(r))
            for s in output
        )
    ]
