"""Command line: ``scbm solve MATRIX`` and ``scbm analyze MATRIX``."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

import scbm


def _solve(args: argparse.Namespace) -> dict:
    result = scbm.solve(json.loads(args.matrix), solver=args.solver)
    return {"cost": result.cost, "permutation": result.permutation}


def _analyze(args: argparse.Namespace) -> dict:
    report = scbm.analyze(json.loads(args.matrix), solver=args.solver)
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
    histories = read_histories(args.nhx)
    orders = read_leaf_orders(args.leaf_orders) if args.leaf_orders else {}
    result = compare_histories(
        histories,
        costs,
        orders,
        mode=args.mode,
        leaf_weight=args.leaf_weight,
        allow_reverse=not args.respect_leaf_direction,
    )
    return {
        "cost_model": asdict(costs),
        "objective": args.mode,
        "allow_leaf_reversal": not args.respect_leaf_direction,
        "leaf_weight": args.leaf_weight if args.mode == "weighted" else None,
        "histories": [
            {
                "solution": h.name,
                "reported_inout_cost": h.input_cost,
                "recomputed_inout_cost": h.inout_cost(costs),
                "families": list(h.families),
                "event_rows": len(h.matrix),
            }
            for h in histories
        ],
        "results": [asdict(r) for r in result],
    }


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
        command.set_defaults(run=run)
    history = commands.add_parser("history", help="compare InOutParsimony NHX histories")
    history.add_argument("nhx", help="InOutParsimony output (one or more solutions)")
    history.add_argument("--leaf-orders", help="JSON file mapping leaf names to ordered families")
    history.add_argument(
        "--respect-leaf-direction",
        action="store_true",
        help="count reversed adjacent pairs as broken",
    )
    history.add_argument("--mode", choices=("pareto", "weighted"), default="pareto")
    history.add_argument(
        "--leaf-weight", type=int, default=1, help="weight per broken adjacency in weighted mode"
    )
    history.add_argument("--loss-open", type=int, default=1)
    history.add_argument("--loss-ext", type=int, default=0)
    history.add_argument("--gain-open", type=int, default=1)
    history.add_argument("--gain-ext", type=int, default=0)
    history.set_defaults(run=_history)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(args.run(args)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
