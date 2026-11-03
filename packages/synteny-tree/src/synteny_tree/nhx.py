"""Read InOutParsimony NHX histories as synteny trees and event matrices.

The ``solutions show`` output of InOutParsimony gives one Newick tree per
solution, with the content of every node in a ``contents`` annotation. This
module parses those records, rejects histories that are not single-origin, and
builds the event matrix of :func:`synteny_tree.event_matrix`. The result is
independent of the SC1P and SCBM objectives: its matrix can be passed directly
to ``sc1p.solve`` or ``scbm.solve``.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sowing import Node
from sowing.repr.newick import parse

from synteny_tree import Matrix, _nodes, event_matrix
from synteny_tree.leaf_orders import index_leaf_orders


@dataclass(frozen=True)
class EventCosts:
    """InOutParsimony costs: ``open + extension * size`` for each segment."""

    loss_open: int = 1
    loss_ext: int = 0
    gain_open: int = 1
    gain_ext: int = 0

    def __post_init__(self):
        if any(
            not isinstance(x, int) or isinstance(x, bool) or x < 0
            for x in (self.loss_open, self.loss_ext, self.gain_open, self.gain_ext)
        ):
            raise ValueError("event costs must be non-negative integers")


@dataclass(frozen=True)
class HistoryInstance:
    name: str
    tree: Node
    contents: dict[str, frozenset[str]]
    families: tuple[str, ...]
    matrix: Matrix
    loss_rows: int
    input_cost: float | None

    def row_costs(self, costs: EventCosts) -> tuple[list[int], list[int]]:
        losses, gains = self.loss_rows, len(self.matrix) - self.loss_rows
        return (
            [costs.loss_open] * losses + [costs.gain_open] * gains,
            [costs.loss_ext] * losses + [costs.gain_ext] * gains,
        )

    def inout_cost(self, costs: EventCosts) -> int:
        opens, extensions = self.row_costs(costs)
        return sum(o + e * row.count(1) for row, o, e in zip(self.matrix, opens, extensions))

    def leaf_columns(self, orders: Mapping[str, Sequence[str]]) -> list[list[int]]:
        leaves = {_name(node) for node in _nodes(self.tree) if not node.edges}
        leaf_contents = {name: self.contents[name] for name in leaves}
        return index_leaf_orders(orders, leaf_contents, self.families)


def _name(node: Node[Any, Any]) -> str:
    name = node.data
    if not isinstance(name, str):
        raise TypeError("each history node must have a string name")
    return name


def _convert(node: Node[Any, Any], contents: dict[str, frozenset[str]]) -> Node[str, Any]:
    fields = dict(node.data or {})
    name = fields.get("name")
    if not isinstance(name, str) or not name or name in contents or "contents" not in fields:
        raise ValueError("every node must have a unique name and contents")
    content = frozenset(ast.literal_eval(fields["contents"]))
    if any(not isinstance(x, str) for x in content):
        raise ValueError("family labels must be strings")
    contents[name] = content
    result = Node(name)
    for edge in node.edges:
        result = result.add(_convert(edge.node, contents))
    return result


def _family_key(s: str):
    match = re.match(r"(\d+)(.*)", s)
    return (int(match.group(1)), match.group(2)) if match else (10**9, s)


def read_histories(path: str | Path) -> list[HistoryInstance]:
    """Read all ``# solution no. ...`` NHX records in an InOutParsimony output."""
    text = Path(path).read_text()
    chunks = re.split(r"(?m)^#\s*solution no\.\s*(\d+)\s*,\s*cost=([^\s]+)\s*$", text)
    if len(chunks) == 1:
        chunks = ["", "1", "", text]
    results = []
    for i in range(1, len(chunks), 3):
        number, reported, data = chunks[i : i + 3]
        source = "\n".join(line for line in data.splitlines() if not line.lstrip().startswith("#"))
        raw = parse(source)
        contents: dict[str, frozenset[str]] = {}
        counts: dict[str, int] = {}

        tree = _convert(raw, contents)
        families = tuple(sorted({g for c in contents.values() for g in c}, key=_family_key))
        for node in _nodes(tree):
            parent = contents[_name(node)]
            for edge in node.edges:
                for family in contents[_name(edge.node)] - parent:
                    counts[family] = counts.get(family, 0) + 1
        for family in contents[_name(tree)]:
            counts[family] = counts.get(family, 0) + 1
        if any(counts.get(family, 0) != 1 for family in families):
            raise ValueError("history is not single-origin; occurrence expansion is required")
        matrix = event_matrix(tree, contents, families=families)
        loss_rows = sum(
            bool(contents[_name(n)] - contents[_name(e.node)])
            for n in _nodes(tree)
            for e in n.edges
        )
        try:
            reported_cost = float(reported) if reported else None
        except ValueError as error:
            raise ValueError(f"invalid InOutParsimony cost {reported!r}") from error
        results.append(
            HistoryInstance(
                number,
                tree,
                contents,
                families,
                matrix,
                loss_rows,
                reported_cost,
            )
        )
    return results
