"""Observed leaf orders and their ternary adjacency constraints."""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping, Sequence
from itertools import pairwise
from pathlib import Path
from typing import TypeAlias

Matrix: TypeAlias = list[list[int]]
LeafOrders: TypeAlias = Mapping[str, Sequence[str]]


def read_leaf_orders(path: str | Path) -> dict[str, tuple[str, ...]]:
    """Read a JSON mapping from leaf names to ordered family labels."""
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict) or any(not isinstance(k, str) for k in data):
        raise ValueError("leaf orders must be a JSON object mapping leaf names to arrays")
    orders = {}
    for leaf, order in data.items():
        if not isinstance(order, list) or any(not isinstance(f, str) for f in order):
            raise ValueError(f"leaf order for {leaf!r} must be an array of family labels")
        if len(set(order)) != len(order):
            raise ValueError(f"leaf order for {leaf!r} contains duplicate families")
        orders[leaf] = tuple(order)
    return orders


def index_leaf_orders(
    orders: LeafOrders,
    leaf_contents: Mapping[str, Collection[str]],
    families: Sequence[str],
) -> list[list[int]]:
    """Validate observed leaf orders and convert family labels to columns."""
    indices = {family: i for i, family in enumerate(families)}
    if len(indices) != len(families):
        raise ValueError("family labels must be unique")
    result = []
    for leaf, order in orders.items():
        if leaf not in leaf_contents:
            raise ValueError(f"{leaf!r} is not a leaf")
        if len(set(order)) != len(order) or set(order) != set(leaf_contents[leaf]):
            raise ValueError(f"leaf order for {leaf!r} must contain exactly its families")
        try:
            result.append([indices[family] for family in order])
        except KeyError as error:
            raise ValueError(f"unknown family {error.args[0]!r} in leaf order for {leaf!r}") from error
    return result


def adjacency_rows(n: int, leaf_orders: Sequence[Sequence[int]]) -> Matrix:
    """Encode consecutive leaf families as ternary rows over ``n`` columns."""
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ValueError("n must be a non-negative integer")
    rows: Matrix = []
    for order in leaf_orders:
        if any(not isinstance(i, int) or isinstance(i, bool) or i < 0 or i >= n for i in order):
            raise ValueError("leaf orders must contain valid integer column indices")
        if len(set(order)) != len(order):
            raise ValueError("a leaf order cannot contain duplicate families")
        content = set(order)
        for left, right in pairwise(order):
            rows.append([1 if j in (left, right) else 0 if j in content else 2 for j in range(n)])
    return rows
