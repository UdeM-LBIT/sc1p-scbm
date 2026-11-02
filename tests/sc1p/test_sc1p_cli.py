from __future__ import annotations

import json

from sc1p.cli import main


def _run(capsys, *argv: str):
    assert main(list(argv)) == 0
    return json.loads(capsys.readouterr().out)


def test_solve(capsys):
    out = _run(capsys, "[[1,0,1],[0,1,2]]", "--solver", "brute_force")
    assert out["satisfiable"] is True
    assert sorted(out["permutation"]) == [0, 1, 2]


def test_unsatisfiable(capsys):
    out = _run(capsys, "[[1,0,1],[0,1,1],[1,1,0]]", "--solver", "brute_force")
    assert out == {"satisfiable": False, "permutation": None}


def test_all(capsys):
    assert len(_run(capsys, "[[1,1,0]]", "--all", "--solver", "brute_force")) == 4
