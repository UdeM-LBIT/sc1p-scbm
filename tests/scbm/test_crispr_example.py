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
COSTS = ["--loss-open", "20", "--loss-ext", "10", "--gain-open", "1", "--gain-ext", "0"]


def run_history(*options):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scbm.cli",
            "history",
            str(EXAMPLE / "crispr-class1-out-lo20-le10-go1.out.nhx"),
            *COSTS,
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
    assert report["histories"][0]["reported_inout_cost"] == 613
    assert report["histories"][0]["recomputed_inout_cost"] == 613
    assert [(r["history_cost"], r["block_count"]) for r in report["results"]] == [(653, 19)]


@pytest.mark.parametrize("respect_direction", [False, True])
def test_documented_pareto_example(respect_direction):
    flags = ["--leaf-orders", str(EXAMPLE / "leaf-orders-two.json"), "--mode", "pareto"]
    if respect_direction:
        flags.append("--respect-leaf-direction")
    report = run_history(*flags)
    assert report["allow_leaf_reversal"] is not respect_direction
    assert {(r["history_cost"], r["broken_adjacencies"]) for r in report["results"]} == {
        (673, 1),
        (653, 2),
    }


def test_documented_weighted_example():
    report = run_history(
        "--leaf-orders",
        str(EXAMPLE / "leaf-orders-two.json"),
        "--mode",
        "weighted",
        "--leaf-weight",
        "25",
    )
    (result,) = report["results"]
    assert (result["history_cost"], result["broken_adjacencies"]) == (673, 1)
