"""Command line: ``scbm solve MATRIX`` and ``scbm analyze MATRIX``."""

from __future__ import annotations

import argparse
import json
import sys

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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(args.run(args)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
