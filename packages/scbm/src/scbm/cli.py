"""Command line: ``scbm solve MATRIX`` and ``scbm analyze MATRIX``."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace

import scbm


def _matrix(value: str) -> list[list]:
    matrix = json.loads(value)
    if not isinstance(matrix, list) or any(not isinstance(row, list) for row in matrix):
        raise ValueError("matrix must be a JSON array of row arrays")
    if any(isinstance(cell, (list, dict)) for row in matrix for cell in row):
        raise ValueError("matrix entries must be 0, 1 or 2")
    return matrix


def _solve(args: argparse.Namespace) -> dict:
    result = scbm.solve(_matrix(args.matrix), solver=args.solver)
    return {"cost": result.cost, "permutation": result.permutation}


def _analyze(args: argparse.Namespace) -> dict:
    report = scbm.analyze(_matrix(args.matrix), solver=args.solver)
    return {
        "has_sc1p": report.has_sc1p,
        "cost": report.cost,
        "permutation": report.permutation,
    }


def _history(args: argparse.Namespace) -> dict:
    from scbm.history import compare_histories
    from synteny_tree.leaf_orders import read_leaf_orders
    from synteny_tree.nhx import EventCosts, read_histories

    costs = EventCosts(args.loss_open, args.loss_ext, args.gain_open, args.gain_ext)
    histories = []
    sources = {}
    groups = []
    for file_index, path in enumerate(args.nhx, 1):
        group = []
        for solution_index, history in enumerate(read_histories(path), 1):
            if len(args.nhx) > 1:
                history = replace(history, name=f"{file_index}.{solution_index} ({history.name})")
            histories.append(history)
            group.append(history)
            sources[history.name] = (path, file_index)
        groups.append(group)
    orders = read_leaf_orders(args.leaf_orders) if args.leaf_orders else {}
    leaf_weight = args.leaf_weight if args.leaf_weight is not None else 1
    progress = None
    if sys.stderr.isatty():

        def progress(index: int, total: int, name: str) -> None:
            print(f"Solving history {index}/{total}: {name}...", file=sys.stderr, flush=True)

    result = []
    for group in [histories] if args.global_front else groups:
        result.extend(
            compare_histories(
                group,
                costs,
                orders,
                mode=args.mode,
                leaf_weight=leaf_weight,
                allow_reverse=not args.respect_leaf_direction,
                enumerate_all=args.all,
                leaf_criterion=args.leaf_criterion,
                progress=progress,
            )
        )
    report = {
        "cost_model": asdict(costs),
        "objective": args.mode,
        "allow_leaf_reversal": not args.respect_leaf_direction,
        "orders_up_to_reversal": not args.respect_leaf_direction
        or not any(len(order) >= 2 for order in orders.values()),
        "leaf_weight": leaf_weight if args.mode == "weighted" else None,
        "histories": [
            {
                "solution": h.name,
                **(
                    {"source": sources[h.name][0], "source_index": sources[h.name][1]}
                    if len(args.nhx) > 1
                    else {}
                ),
                "reported_inout_cost": h.input_cost,
                "recomputed_inout_cost": h.inout_cost(costs),
                "families": list(h.families),
                "event_rows": len(h.matrix),
            }
            for h in histories
        ],
        "results": [
            {k: v for k, v in asdict(r).items() if v is not None}
            for r in (result if args.all else _representatives(result))
        ],
    }
    if args.leaf_criterion == "extension":
        report["leaf_criterion"] = "extension"
    if args.global_front:
        report["global_front"] = True
    if orders:
        report["leaf_orders"] = orders
    if args.tree:
        report["trees"] = [
            {"history": h.name, "root": _tree_node(h.tree, h.contents, h.families)}
            for h in histories
        ]
    return report


def _representatives(results: list) -> list:
    seen = set()
    unique = []
    for result in results:
        key = (
            result.history,
            result.history_cost,
            result.extension_cost
            if result.extension_cost is not None
            else result.broken_adjacencies,
        )
        if key not in seen:
            seen.add(key)
            unique.append(result)
    return unique


def _pair_rows(results: list) -> list:
    seen = set()
    unique = []
    for result in results:
        key = (
            result.get("history"),
            result["history_cost"],
            result.get("extension_cost", result["broken_adjacencies"]),
            result["block_count"],
        )
        if key not in seen:
            seen.add(key)
            unique.append(result)
    return unique


def _tree_node(
    node, contents: dict, families: tuple[str, ...], parent: frozenset[str] = frozenset()
) -> dict:
    here = contents[node.data]
    return {
        "name": node.data,
        "contents": [family for family in families if family in here],
        "lost": [family for family in families if family in parent and family not in here],
        "gained": [family for family in families if family in here and family not in parent],
        "children": [_tree_node(edge.node, contents, families, here) for edge in node.edges],
    }


def pretty(value: object, indent: int = 0) -> str:
    """Readable rendering: nested dicts/lists on their own lines, scalar lists inline."""
    pad = "  " * indent
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = [f"{pad}  {json.dumps(k)}: {pretty(v, indent + 1)}" for k, v in value.items()]
        return "{\n" + ",\n".join(items) + f"\n{pad}}}"
    if isinstance(value, list):
        inner = [pretty(v, indent + 1) for v in value]
        if len(value) <= 12 and all(not isinstance(v, (dict, list)) for v in value):
            return "[" + ", ".join(inner) + "]"
        return "[\n" + ",\n".join(f"{pad}  {v}" for v in inner) + f"\n{pad}]"
    return json.dumps(value)


def _cell(value: object) -> str:
    if isinstance(value, (list, tuple)):
        return " ".join(_cell(v) for v in value)
    if isinstance(value, dict):
        return " ".join(f"{k}={_cell(v)}" for k, v in value.items())
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float) and value.is_integer():
        return f"{value:.0f}"
    return str(value)


def _render(report: dict, console) -> None:
    """One line per scalar, one compact table per list of records."""
    from rich.table import Table

    for key, value in report.items():
        if isinstance(value, list) and any(isinstance(v, dict) for v in value):
            columns = list(dict.fromkeys(k for row in value for k in row))
            columns.sort(key=lambda c: isinstance(value[0].get(c), (list, tuple)))
            table = Table(box=None, pad_edge=False, header_style="bold")
            for column in columns:
                table.add_column(column, no_wrap=True)
            for row in value:
                table.add_row(*(_cell(row.get(c)) for c in columns))
            console.print(table)
        else:
            console.print(f"[bold]{key}[/bold]  {_cell(value)}")


def _render_history(report: dict, console) -> None:
    """Terminal report: header lines, solutions table, family orders."""
    from rich.markup import escape
    from rich.table import Table

    if not report.get("global_front") and any(
        "source_index" in history for history in report["histories"]
    ):
        indices = dict.fromkeys(history["source_index"] for history in report["histories"])
        for index in indices:
            histories = [h for h in report["histories"] if h["source_index"] == index]
            names = {h["solution"] for h in histories}
            subset = dict(report)
            subset["histories"] = [
                {k: v for k, v in h.items() if k != "source_index"} for h in histories
            ]
            for field in ("results", "trees"):
                if field in report:
                    subset[field] = [entry for entry in report[field] if entry["history"] in names]
            _render_history(subset, console)
        return

    leaf_orders = report.get("leaf_orders") or {}
    objective = report["objective"].upper() if leaf_orders else "OPTIMAL HISTORY"
    console.rule(f"[bold cyan]SCBM / HISTORY ANALYSIS[/] [cyan]· {objective}[/]", style="cyan")

    model = " · ".join(f"{k.replace('_', ' ')} {_cell(v)}" for k, v in report["cost_model"].items())
    console.print(f"[bold cyan]cost model[/]  {model}")

    for history in report["histories"]:
        reported = history["reported_inout_cost"]
        recomputed = history["recomputed_inout_cost"]
        if reported is None:
            cost = f"cost: [bold]{_cell(recomputed)}[/] (not reported in NHX)"
        elif reported == recomputed:
            cost = f"[green]✓[/] cost verified: [bold]{_cell(recomputed)}[/]"
        else:
            cost = f"[yellow]![/] cost: [bold]{_cell(recomputed)}[/] (reported {_cell(reported)})"
        line = f"{cost} · {len(history['families'])} families · {history['event_rows']} events"
        if leaf_orders:
            reversal = "enabled" if report["allow_leaf_reversal"] else "disabled"
            line += f" · leaf reversal {reversal}"
        if leaf_orders and report["leaf_weight"] is not None:
            line += f" · leaf weight {report['leaf_weight']}"
        console.print(f"[bold cyan]history {escape(str(history['solution']))}[/]  {line}")
        if history.get("source"):
            console.print(f"  [dim]file: {escape(str(history['source']))}[/]")

    if leaf_orders:
        console.print(f"[bold cyan]observed leaf orders[/]  {len(leaf_orders)} leaves")

    results = report["results"]
    if not results:
        return

    pairs = _pair_rows(results)
    multiple = len(report["histories"]) > 1
    if not leaf_orders:
        header = "[bold cyan]OPTIMAL RESULTS[/]"
    elif report["objective"] == "pareto":
        points = {
            (r["history_cost"], r.get("extension_cost", r["broken_adjacencies"])) for r in pairs
        }
        header = f"[bold cyan]PARETO FRONT[/] [dim]{len(points)} points[/]"
        if len(points) != len(pairs):
            header += f" [dim]· {len(pairs)} history results[/]"
        if len(pairs) != len(results):
            header += f" [dim]· {len(results)} orders[/]"
    else:
        header = "[bold cyan]WEIGHTED RESULT[/]"
    console.print(header)
    table = Table(box=None, header_style="bold cyan", pad_edge=False)
    table.add_column("#", justify="right")
    if multiple:
        table.add_column("history")
    table.add_column("history cost", justify="right")
    if report.get("leaf_criterion") == "extension":
        table.add_column("extension cost", justify="right")
        table.add_column("total cost", justify="right")
    elif leaf_orders:
        table.add_column("broken adjacencies", justify="right")
    table.add_column("orders at point" if leaf_orders else "optimal orders", justify="right")
    for index, result in enumerate(pairs, 1):
        row = [str(index)]
        if multiple:
            row.append(escape(str(result["history"])))
        row.append(_cell(result["history_cost"]))
        if report.get("leaf_criterion") == "extension":
            row.extend([str(result["extension_cost"]), str(result["total_cost"])])
        elif leaf_orders:
            row.append(str(result["broken_adjacencies"]))
        row.append(_cell(result.get("solutions")))
        table.add_row(*row)
    console.print(table)
    if report.get("orders_up_to_reversal"):
        console.print("[dim]Orders and counts are shown up to reversal.[/]")
    if report["objective"] == "weighted" and any("solutions" not in r for r in pairs):
        console.print("[dim]-: not counted; use --all to enumerate optimal orders.[/]")

    console.print("\n[bold cyan]FAMILY ORDERS BY RESULT[/]")
    console.print("[dim]Each group corresponds to a numbered row above.[/]")
    for index, point in enumerate(pairs, 1):
        group = [
            result
            for result in results
            if all(
                result.get(key) == point.get(key)
                for key in (
                    "history",
                    "history_cost",
                    "extension_cost"
                    if report.get("leaf_criterion") == "extension"
                    else "broken_adjacencies",
                    "block_count",
                )
            )
        ]
        history = f" · history {escape(str(point['history']))}" if multiple else ""
        console.print(f"[bold]Result {index}{history}[/]  [dim]{len(group)} shown[/]")
        for order_index, result in enumerate(group, 1):
            order = "  ".join(escape(_cell(family)) for family in result["order"])
            console.print(f"  [dim]{order_index}.[/]  {order}")

    _render_trees(report.get("trees") or [], console)


def _render_trees(trees: list[dict], console) -> None:
    """One Rich tree per history: node name, contents, losses and gains."""
    from rich.markup import escape
    from rich.tree import Tree

    def build(data: dict) -> Tree:
        label = f"[bold]{escape(str(data['name']))}[/]"
        if data["contents"]:
            label += "  [dim]" + escape("  ".join(data["contents"])) + "[/]"
        counts = []
        if data["lost"]:
            counts.append(f"[red]lost families: {len(data['lost'])}[/]")
        if data["gained"]:
            counts.append(f"[green]gained families: {len(data['gained'])}[/]")
        if counts:
            label += "  " + " · ".join(counts)
        branch = Tree(label)
        for child in data["children"]:
            branch.add(build(child))
        return branch

    for entry in trees:
        console.print(
            f"[bold cyan]INPUT TREE · {escape(str(entry['history']))}[/]"
            "  [dim]input contents and changed families, before ordering[/]"
        )
        console.print(build(entry["root"]))


def _emit(report: dict, output_format: str, command: str) -> None:
    """Render a report: ``rich`` tables, or plain JSON for pipes and scripts."""
    requested_format = output_format
    if output_format == "auto":
        output_format = "rich" if sys.stdout.isatty() else "json"
    if output_format == "rich":
        try:
            from rich.console import Console
        except ImportError:
            if requested_format == "rich":
                raise ValueError(
                    "rich is not installed; run `pip install 'scbm[cli]'` or pass --format json"
                ) from None
        else:
            (_render_history if command == "history" else _render)(report, Console(soft_wrap=True))
            return
    print(pretty(report))


def _add_format(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--format",
        choices=("auto", "json", "rich"),
        default="auto",
        dest="format",
        help="output: 'auto' (rich on a terminal, JSON otherwise), 'json', or 'rich'",
    )


def _nonnegative(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a non-negative integer") from None
    if number < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scbm", description="Minimize the number of maximal blocks of a ternary matrix."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name, run, help_text in (
        ("solve", _solve, "minimum active-block count and an optimal column order"),
        ("analyze", _analyze, "SC1P verdict from the SCBM optimum"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("matrix", help="JSON matrix, e.g. '[[1,0,1],[0,1,2]]'")
        command.add_argument("--solver", default="auto", help="backend name, or 'auto'")
        _add_format(command)
        command.set_defaults(run=run)
    history = commands.add_parser("history", help="compare InOutParsimony NHX histories")
    history.add_argument(
        "nhx", nargs="+", help="InOutParsimony output files (each may contain several solutions)"
    )
    history.add_argument("--leaf-orders", help="JSON file mapping leaf names to ordered families")
    history.add_argument(
        "--leaf-criterion",
        choices=("adjacency", "extension"),
        default="adjacency",
        help="Pareto criterion: broken adjacencies (default) or pair-loss cost; extension allows reversal",
    )
    history.add_argument(
        "--global-front", action="store_true", help="compare histories across all input files"
    )
    history.add_argument(
        "--tree", action="store_true", help="include the input history tree before ordering"
    )
    history.add_argument(
        "--all",
        action="store_true",
        help="return optimal orders (up to reversal when equivalent); Pareto counts them even without this flag",
    )
    history.add_argument(
        "--respect-leaf-direction",
        action="store_true",
        help="count reversed adjacent pairs as broken",
    )
    history.add_argument(
        "--mode",
        choices=("pareto", "weighted"),
        default="pareto",
        help="comparison objective (default: pareto)",
    )
    history.add_argument(
        "--leaf-weight",
        type=_nonnegative,
        default=None,
        help="weight per broken adjacency in weighted mode (default: 1)",
    )
    history.add_argument(
        "--loss-open", type=_nonnegative, default=1, help="cost per loss block (default: 1)"
    )
    history.add_argument(
        "--loss-ext", type=_nonnegative, default=0, help="cost per lost family (default: 0)"
    )
    history.add_argument(
        "--gain-open", type=_nonnegative, default=1, help="cost per gain block (default: 1)"
    )
    history.add_argument(
        "--gain-ext", type=_nonnegative, default=0, help="cost per gained family (default: 0)"
    )
    _add_format(history)
    history.set_defaults(run=_history)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.format == "rich":
        try:
            __import__("rich.console")
        except ImportError:
            parser.error(
                "rich is not installed; run `pip install 'scbm[cli]'` or pass --format json"
            )
    if args.command == "history":
        if args.leaf_weight is not None and args.mode != "weighted":
            parser.error("--leaf-weight requires --mode weighted")
        if args.leaf_criterion == "extension" and args.mode != "pareto":
            parser.error("--leaf-criterion extension requires --mode pareto")
        if args.leaf_criterion == "extension" and args.respect_leaf_direction:
            parser.error("--leaf-criterion extension cannot be used with --respect-leaf-direction")
    try:
        _emit(args.run(args), args.format, args.command)
    except (ValueError, OSError, ImportError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    sys.exit(main())
