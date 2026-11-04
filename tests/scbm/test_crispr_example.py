"""End-to-end checks for the documented CRISPR example commands."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("pysat")
pytest.importorskip("sowing")

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "crispr-class1"
ARCHIVE_DATA = ROOT / "results" / "pareto-24"
COSTS = ["--loss-open", "20", "--loss-ext", "10", "--gain-open", "1", "--gain-ext", "0"]
ARCHIVE_COSTS = ["--loss-open", "1", "--loss-ext", "1", "--gain-open", "1", "--gain-ext", "0"]


def run_history(*options, input_file=None, costs=COSTS):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scbm.cli",
            "history",
            str(input_file or EXAMPLE / "crispr-class1-out-lo20-le10-go1.out.nhx"),
            *costs,
            *options,
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return json.loads(result.stdout)


def test_documented_example_without_leaf_orders():
    report = run_history()
    assert report["histories"][0]["reported_inout_cost"] == 574
    assert report["histories"][0]["recomputed_inout_cost"] == 574
    assert [(r["history_cost"], r["block_count"]) for r in report["results"]] == [(574, 18)]


@pytest.fixture
def archive_solution(tmp_path):
    """Use solution 4 from the eight histories in emeric(deux).zip."""
    lines = (
        (ARCHIVE_DATA / "crispr-class1-resolvI-III-out-lo1-le1-go1.nhx").read_text().splitlines()
    )
    path = tmp_path / "solution.nhx"
    path.write_text("# count=1\n" + "\n".join(lines[7:9]) + "\n")
    return path


PARETO = {(46, 22): 3, (44, 23): 3, (43, 26): 1}
PARETO_DIRECTED = {(46, 27): 2, (44, 28): 1, (43, 37): 5}


@pytest.mark.parametrize("respect_direction", [False, True])
def test_documented_pareto_example(respect_direction, archive_solution):
    flags = ["--leaf-orders", str(ARCHIVE_DATA / "crispr-class1-order.json"), "--mode", "pareto"]
    if respect_direction:
        flags.append("--respect-leaf-direction")
    report = run_history(*flags, input_file=archive_solution, costs=ARCHIVE_COSTS)
    assert report["leaf_orders"]["IV-B"] == ["8", "11", "7", "5"]
    assert report["allow_leaf_reversal"] is not respect_direction
    expected = PARETO_DIRECTED if respect_direction else PARETO
    got = {(r["history_cost"], r["broken_adjacencies"]): r["solutions"] for r in report["results"]}
    assert got == expected


def test_documented_weighted_example(archive_solution):
    report = run_history(
        "--leaf-orders",
        str(ARCHIVE_DATA / "crispr-class1-order.json"),
        "--mode",
        "weighted",
        "--leaf-weight",
        "25",
        input_file=archive_solution,
        costs=ARCHIVE_COSTS,
    )
    (result,) = report["results"]
    assert result["history_cost"] == 46
    assert result["broken_adjacencies"] == 22


def test_all_option(archive_solution):
    flags = ["--leaf-orders", str(ARCHIVE_DATA / "crispr-class1-order.json"), "--mode", "pareto"]
    base = run_history(*flags, input_file=archive_solution, costs=ARCHIVE_COSTS)
    every = run_history(*flags, "--all", input_file=archive_solution, costs=ARCHIVE_COSTS)
    assert len(every["results"]) == 7
    assert sum(r["solutions"] for r in base["results"]) == 7
    pairs = {(r["history_cost"], r["broken_adjacencies"]): r["solutions"] for r in base["results"]}
    every_pairs = {(r["history_cost"], r["broken_adjacencies"]) for r in every["results"]}
    assert every_pairs == set(pairs)
    assert all(
        r["solutions"] == pairs[(r["history_cost"], r["broken_adjacencies"])]
        for r in every["results"]
    )
    orders = [tuple(r["order"]) for r in every["results"]]
    assert len(set(orders)) == len(orders)
    assert not any(order[::-1] in set(orders) for order in orders)


def test_tree_option():
    report = run_history("--tree")
    (tree,) = report["trees"]
    root = tree["root"]
    families = report["histories"][0]["families"]
    assert root["name"]
    assert set(root["contents"]) < set(families)
    assert root["contents"] == [family for family in families if family in root["contents"]]
    assert root["lost"] == []
    assert root["gained"] == root["contents"]
    assert root["children"]
    leaves = [node for node in _walk(root) if not node["children"]]
    assert any(leaf["lost"] for leaf in leaves)
    assert "trees" not in run_history()


def _walk(node):
    yield node
    for child in node["children"]:
        yield from _walk(child)
