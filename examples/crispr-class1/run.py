"""SCBM on the CRISPR-Cas class 1 synteny tree of the paper's supplement.

Usage: uv run --all-extras python examples/crispr-class1/run.py [tree.nhx]

The NHX synteny tree gives the content of every node (``contents``), as
inferred by InOutParsimony. The script builds the event matrix, solves SCBM
with the MaxSAT backend and times the solver call (10 warm-up calls, then 100
measured calls). NHX parsing and matrix construction are not timed.
"""

from __future__ import annotations

import ast
import json
import re
import statistics
import sys
import time
from pathlib import Path

from sowing import Node
from sowing.repr.newick import parse

import scbm
from scbm.score import block_cost, block_lower_bound
from synteny_tree import event_matrix

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "crispr-class1-out-lo20-le10-go1.out.nhx"
WARMUP, MEASURED = 10, 100


def load(path: Path) -> Node:
    lines = path.read_text().splitlines()
    return parse("".join(line for line in lines if not line.lstrip().startswith("#")))


def relabel(node: Node, contents: dict[str, frozenset[str]]) -> Node:
    data = dict(node.data) if node.data else {}
    name = data.get("name", "")
    contents[name] = frozenset(ast.literal_eval(data.get("contents", "()")))
    out = Node(name)
    for edge in node.edges:
        out = out.add(relabel(edge.node, contents))
    return out


def natural_key(family: str) -> tuple[int, str]:
    match = re.match(r"(\d+)(.*)", family)
    return (int(match.group(1)), match.group(2)) if match else (10**9, family)


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    contents: dict[str, frozenset[str]] = {}
    tree = relabel(load(path), contents)
    families = sorted({g for c in contents.values() for g in c}, key=natural_key)
    matrix = event_matrix(tree, contents, families=families)

    for _ in range(WARMUP):
        scbm.solve(matrix, solver="maxsat")
    result = scbm.solve(matrix, solver="maxsat")
    times_ms = []
    for _ in range(MEASURED):
        start = time.perf_counter_ns()
        result = scbm.solve(matrix, solver="maxsat")
        times_ms.append((time.perf_counter_ns() - start) / 1e6)

    report = {
        "instance": path.name,
        "families": families,
        "shape": [len(matrix), len(families)],
        "lower_bound": block_lower_bound(matrix),
        "identity_cost": block_cost(matrix, list(range(len(families)))),
        "optimum": result.cost,
        "optimal_order": [families[i] for i in result.permutation],
        "mean_ms": statistics.mean(times_ms),
        "sample_standard_deviation_ms": statistics.stdev(times_ms),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
