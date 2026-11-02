"""Block cost on hand-checked rows."""

from __future__ import annotations

import subprocess
import sys

import pytest

from scbm.score import block_cost


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ([1, 0, 0], 1),
        ([1, 1, 0], 1),
        ([1, 0, 1], 2),
        ([1, 2, 1], 1),
        ([2, 0, 2], 0),
        ([1, 0, 2, 0, 1], 2),
        ([1, 0, 1, 0, 1], 3),
    ],
)
def test_single_row(row, expected):
    assert block_cost([row], list(range(len(row)))) == expected


def test_rows_add_up():
    matrix = [
        [1, 0, 1, 0, 1],
        [1, 2, 0, 2, 1],
        [0, 0, 0, 0, 0],
    ]
    assert block_cost(matrix, [0, 1, 2, 3, 4]) == 5


def test_permutation_is_applied():
    assert block_cost([[1, 0, 1]], [0, 2, 1]) == 1


def test_import_loads_no_optional_dependency():
    code = """
import sys
import sc1p, scbm
for name in (
    "pysat",
    "sowing",
    "argparse",
    "random",
    "sc1p.solvers.sat",
    "scbm.exact.maxsat",
):
    assert name not in sys.modules, name
"""
    subprocess.run([sys.executable, "-c", code], check=True)
