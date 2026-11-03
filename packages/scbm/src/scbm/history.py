"""Compare InOutParsimony histories under the SCBM objective.

The NHX records and their event matrices come from :mod:`synteny_tree.nhx`;
this module only searches column orders, optionally trading history cost
against broken observed leaf adjacencies.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from scbm.leaf_orders import LeafResult, pareto_front, solve_weighted
from synteny_tree.nhx import EventCosts, HistoryInstance


@dataclass(frozen=True)
class CandidateResult:
    history: str
    inout_cost: float | None
    order: tuple[str, ...]
    history_cost: int
    broken_adjacencies: int
    block_count: int


def compare_histories(
    histories: Sequence[HistoryInstance],
    costs: EventCosts,
    orders: Mapping[str, Sequence[str]] | None = None,
    *,
    mode: str = "pareto",
    leaf_weight: int = 1,
    allow_reverse: bool = True,
) -> list[CandidateResult]:
    """Compare candidate histories; Pareto uses history cost and leaf disagreement."""
    if mode not in {"pareto", "weighted"}:
        raise ValueError("mode must be 'pareto' or 'weighted'")
    output = []
    for history in histories:
        leaves = history.leaf_columns(orders or {})
        opens, ext = history.row_costs(costs)
        kwargs = {
            "row_open": opens,
            "row_ext": ext,
            "ncols": len(history.families),
            "allow_reverse": allow_reverse,
        }
        found: list[LeafResult] = (
            pareto_front(history.matrix, leaves, **kwargs)
            if mode == "pareto"
            else [solve_weighted(history.matrix, leaves, leaf_weight=leaf_weight, **kwargs)]
        )
        for result in found:
            output.append(
                CandidateResult(
                    history.name,
                    history.input_cost,
                    tuple(history.families[i] for i in result.permutation),
                    result.history_cost,
                    result.broken_adjacencies,
                    result.block_count,
                )
            )
    if mode == "weighted":
        if not output:
            return []
        best = min(r.history_cost + leaf_weight * r.broken_adjacencies for r in output)
        return [r for r in output if r.history_cost + leaf_weight * r.broken_adjacencies == best]
    return [
        r
        for r in output
        if not any(
            s.history_cost <= r.history_cost
            and s.broken_adjacencies <= r.broken_adjacencies
            and (s.history_cost < r.history_cost or s.broken_adjacencies < r.broken_adjacencies)
            for s in output
        )
    ]
