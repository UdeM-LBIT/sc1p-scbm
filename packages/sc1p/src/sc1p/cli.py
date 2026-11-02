"""Command line: ``sc1p MATRIX [--all]``."""

from __future__ import annotations

import argparse
import json
import sys

import sc1p


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sc1p", description="Decide SC1P for a ternary matrix.")
    parser.add_argument("matrix", help="JSON matrix, e.g. '[[1,0,1],[0,1,2]]'")
    parser.add_argument("--solver", default="auto", help="backend name, or 'auto'")
    parser.add_argument("--all", action="store_true", help="print every SC1P order")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    matrix = json.loads(args.matrix)
    if args.all:
        output: object = sc1p.solve_all(matrix, solver=args.solver)
    else:
        result = sc1p.solve(matrix, solver=args.solver)
        output = {"satisfiable": result.satisfiable, "permutation": result.permutation}
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
