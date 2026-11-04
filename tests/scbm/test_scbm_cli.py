from __future__ import annotations

import json
import sys
from io import StringIO

import pytest

from scbm.cli import _render, main, pretty


def _run(capsys, *argv: str):
    assert main(list(argv)) == 0
    return json.loads(capsys.readouterr().out)


def test_solve(capsys):
    out = _run(
        capsys, "solve", "[[1,0,1],[0,1,1],[1,1,0]]", "--solver", "brute_force", "--format", "json"
    )
    assert out["cost"] == 4
    assert sorted(out["permutation"]) == [0, 1, 2]


@pytest.mark.parametrize("command", ["solve", "analyze"])
@pytest.mark.parametrize("matrix", ["null", "[1,2]", "[[[1]]]", "[[{}]]"])
def test_invalid_matrix_structure_is_reported_without_traceback(capsys, command, matrix):
    with pytest.raises(SystemExit) as error:
        main([command, matrix, "--solver", "brute_force"])
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert "matrix" in captured.err
    assert "Traceback" not in captured.err


def test_history_multiple_files_with_same_solution_number(tmp_path, capsys):
    pytest.importorskip("sowing")
    pytest.importorskip("pysat")
    tree = "(A[&contents='(''1'',)'],B[&contents='(''1'',)'])root[&contents='(''1'',)'];"
    paths = [tmp_path / "first.nhx", tmp_path / "second.nhx"]
    paths[0].write_text(f"# solution no. 1, cost=1\n{tree}\n")
    second = tree.replace("(''1'',)", "(''1'', ''2'')")
    paths[1].write_text(f"# solution no. 1, cost=1\n{second}\n")
    report = _run(
        capsys, "history", *(str(path) for path in paths), "--gain-ext", "1", "--format", "json"
    )
    assert [h["source"] for h in report["histories"]] == [str(p) for p in paths]
    assert {r["history"] for r in report["results"]} == {"1.1 (1)", "2.1 (1)"}
    assert {r["history_cost"] for r in report["results"]} == {2, 3}
    global_report = _run(
        capsys,
        "history",
        *(str(path) for path in paths),
        "--gain-ext",
        "1",
        "--global-front",
        "--format",
        "json",
    )
    assert {r["history"] for r in global_report["results"]} == {"1.1 (1)"}


def test_extension_history_report(tmp_path, capsys):
    pytest.importorskip("sowing")
    pytest.importorskip("pysat")
    tree = tmp_path / "tree.nhx"
    tree.write_text(
        "(A[&contents='(''a'', ''b'', ''c'', ''d'')'])"
        "root[&contents='(''a'', ''b'', ''c'', ''d'')'];\n"
    )
    orders = tmp_path / "orders.json"
    orders.write_text(json.dumps({"A": ["a", "b", "c", "d"]}))
    report = _run(
        capsys,
        "history",
        str(tree),
        "--leaf-orders",
        str(orders),
        "--leaf-criterion",
        "extension",
        "--loss-open",
        "3",
        "--loss-ext",
        "2",
        "--format",
        "json",
    )
    assert report["leaf_criterion"] == "extension"
    assert report["results"]
    for result in report["results"]:
        assert result["total_cost"] == result["history_cost"] + result["extension_cost"]
        assert result["extension_cost"] >= 21  # three loss blocks and six lost occurrences

    pytest.importorskip("rich")
    assert (
        main(
            [
                "history",
                str(tree),
                "--leaf-orders",
                str(orders),
                "--leaf-criterion",
                "extension",
                "--format",
                "rich",
            ]
        )
        == 0
    )
    assert "extension cost" in capsys.readouterr().out


def test_weighted_solution_counts(tmp_path, capsys):
    pytest.importorskip("sowing")
    pytest.importorskip("pysat")
    tree = tmp_path / "tree.nhx"
    tree.write_text(
        "(A[&contents='(''a'', ''b'', ''c'')'])root[&contents='(''a'', ''b'', ''c'')'];\n"
    )
    orders = tmp_path / "orders.json"
    orders.write_text(json.dumps({"A": ["a", "b", "c"]}))
    args = (
        "history",
        str(tree),
        "--leaf-orders",
        str(orders),
        "--mode",
        "weighted",
        "--leaf-weight",
        "0",
    )
    single = _run(capsys, *args)
    assert "solutions" not in single["results"][0]
    every = _run(capsys, *args, "--all")
    assert len(every["results"]) == 3
    assert every["orders_up_to_reversal"] is True
    assert {r["broken_adjacencies"]: r["solutions"] for r in every["results"]} == {0: 1, 1: 2}
    directed = _run(capsys, *args, "--all", "--respect-leaf-direction")
    assert directed["orders_up_to_reversal"] is False
    assert len(directed["results"]) == 6


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--loss-open", "-1"], "--loss-open: must be a non-negative integer"),
        (["--leaf-weight", "2"], "--leaf-weight requires --mode weighted"),
        (["--mode", "weighted", "--leaf-criterion", "extension"], "requires --mode pareto"),
        (["--respect-leaf-direction", "--leaf-criterion", "extension"], "cannot be used with"),
    ],
)
def test_invalid_history_options_are_reported_without_traceback(capsys, args, message):
    with pytest.raises(SystemExit) as error:
        main(["history", "unused.nhx", *args])
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert message in captured.err
    assert "Traceback" not in captured.err
    assert not captured.out


def test_explicit_rich_missing_is_an_error(monkeypatch, capsys):
    import builtins

    original_import = builtins.__import__

    def import_without_rich(name, *args, **kwargs):
        if name == "rich.console":
            raise ImportError("missing rich")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_rich)
    with pytest.raises(SystemExit) as error:
        main(["solve", "[[1,0,1]]", "--solver", "brute_force", "--format", "rich"])
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert "rich is not installed" in captured.err
    assert captured.out == ""


def test_history_progress_is_on_terminal_stderr(tmp_path, capsys, monkeypatch):
    pytest.importorskip("sowing")
    pytest.importorskip("pysat")
    tree = tmp_path / "tree.nhx"
    tree.write_text("A[&contents='(''a'',)'];\n")
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    assert main(["history", str(tree), "--format", "json"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["results"]
    assert "Solving history 1/1" in captured.err


def test_rich_format_when_piped(capsys):
    assert main(["solve", "[[1,0,1]]", "--solver", "brute_force", "--format", "rich"]) == 0
    out = capsys.readouterr().out
    assert "cost" in out and "permutation" in out
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)


def test_pretty_round_trips():
    report = {"cost": 4, "families": ["1", "2"], "results": [{"blocks": 19, "order": [0, 1]}]}
    text = pretty(report)
    assert json.loads(text) == report
    assert '["1", "2"]' in text
    assert '  "cost": 4' in text


def test_rich_render_is_compact():
    pytest.importorskip("rich")
    from rich.console import Console

    report = {"objective": "pareto", "results": [{"cost": 4, "order": [0, 1]}]}
    buffer = StringIO()
    _render(report, Console(file=buffer, width=80, force_terminal=False))
    lines = buffer.getvalue().splitlines()
    assert lines[0].startswith("objective")
    assert lines[1].split() == ["cost", "order"]
    assert lines[2].split() == ["4", "0", "1"]
    assert len(lines) == 3


def test_history_report_sections():
    pytest.importorskip("rich")
    from rich.console import Console

    from scbm.cli import _render_history

    report = {
        "cost_model": {"loss_open": 20, "loss_ext": 10, "gain_open": 1, "gain_ext": 0},
        "objective": "pareto",
        "allow_leaf_reversal": True,
        "leaf_weight": None,
        "histories": [
            {
                "solution": "1",
                "reported_inout_cost": 613.0,
                "recomputed_inout_cost": 613,
                "families": ["1", "2"],
                "event_rows": 17,
            }
        ],
        "results": [
            {
                "history": "1",
                "inout_cost": 613.0,
                "order": ("1", "2"),
                "history_cost": 673,
                "broken_adjacencies": 1,
                "block_count": 20,
            },
            {
                "history": "1",
                "inout_cost": 613.0,
                "order": ("2", "1"),
                "history_cost": 653,
                "broken_adjacencies": 2,
                "block_count": 19,
            },
        ],
        "leaf_orders": {"A": ["1", "2"], "B": ["2", "1"]},
    }
    buffer = StringIO()
    _render_history(report, Console(file=buffer, width=100, force_terminal=False))
    out = buffer.getvalue()
    assert "SCBM / HISTORY ANALYSIS" in out
    assert "cost model" in out and "history 1" in out
    assert "cost verified: 613" in out
    assert "observed leaf orders" in out and "2 leaves" in out
    assert "PARETO FRONT" in out and "FAMILY ORDERS BY RESULT" in out
    assert "orders at point" in out and "Result 2" in out
    assert "blocks" not in out and "broken adjacencies" in out

    report["histories"][0]["reported_inout_cost"] = None
    buffer = StringIO()
    _render_history(report, Console(file=buffer, width=100, force_terminal=False))
    assert "not reported in NHX" in buffer.getvalue()
    assert "cost verified" not in buffer.getvalue()

    report.pop("leaf_orders")
    buffer = StringIO()
    _render_history(report, Console(file=buffer, width=100, force_terminal=False))
    out = buffer.getvalue()
    assert "OPTIMAL RESULTS" in out and "history cost" in out
    assert "PARETO" not in out and "blocks" not in out and "broken adjacencies" not in out


def test_tree_render():
    pytest.importorskip("rich")
    from rich.console import Console

    from scbm.cli import _render_trees

    trees = [
        {
            "history": "1",
            "root": {
                "name": "r",
                "contents": ["1", "2"],
                "lost": [],
                "gained": ["1", "2"],
                "children": [
                    {"name": "u", "contents": ["1"], "lost": ["2"], "gained": [], "children": []}
                ],
            },
        }
    ]
    buffer = StringIO()
    _render_trees(trees, Console(file=buffer, width=60, force_terminal=False))
    text = buffer.getvalue()
    assert "TREE · 1" in text
    assert "r" in text and "u" in text
    assert "1  2" in text
    assert "INPUT TREE" in text and "before ordering" in " ".join(text.split())
    assert "gained families: 2" in text and "lost families: 1" in text


def test_pair_rows_group_identical_pairs():
    from scbm.cli import _pair_rows

    results = [
        {"history_cost": 574, "broken_adjacencies": 0, "block_count": 18, "solutions": 216},
        {"history_cost": 574, "broken_adjacencies": 0, "block_count": 18, "solutions": 216},
        {"history_cost": 574, "broken_adjacencies": 0, "block_count": 17, "solutions": 216},
        {"history_cost": 594, "broken_adjacencies": 1, "block_count": 19, "solutions": 2},
    ]
    rows = _pair_rows(results)
    assert len(rows) == 3
    assert rows[0]["solutions"] == 216


def test_analyze(capsys):
    out = _run(capsys, "analyze", "[[1,0,1]]", "--solver", "brute_force")
    assert out["has_sc1p"]
    assert out["cost"] == 1
