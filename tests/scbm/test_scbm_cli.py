from __future__ import annotations

import json

from scbm.cli import main


def _run(capsys, *argv: str):
    assert main(list(argv)) == 0
    return json.loads(capsys.readouterr().out)


def test_solve(capsys):
    out = _run(capsys, "solve", "[[1,0,1],[0,1,1],[1,1,0]]", "--solver", "brute_force")
    assert out["cost"] == 4
    assert sorted(out["permutation"]) == [0, 1, 2]


def test_analyze(capsys):
    out = _run(capsys, "analyze", "[[1,0,1]]", "--solver", "brute_force")
    assert out["has_sc1p"] is True
    assert out["cost"] == 1
