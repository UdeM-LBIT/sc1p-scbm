"""Generate pgfplots scaling figures from the benchmark CSV exports.

The LaTeX figures read the CSVs with ``\\addplot table``; Parquet is never read
by LaTeX directly. Use ``--csv-prefix`` to match the location of the CSV files
relative to the generated ``.tex``.

Only the median wall time is plotted. The SAT and UNSAT families share one
axis so their scaling can be compared directly; the per-component breakdown
stays in the CSV and database.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

FAMILY_COLORS = {
    "random_sat": "accent",
    "random": "brk",
}


def _n(row: dict[str, str]) -> int:
    try:
        return int(row["n"])
    except (KeyError, ValueError) as exc:
        raise SystemExit(f"invalid n in benchmark CSV row: {row!r}") from exc


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    return sorted(rows, key=_n)


def _family_title(problem: str, family: str) -> str:
    if problem == "sc1p":
        return {"random_sat": "SAT", "random": "UNSAT"}.get(
            family, family.capitalize()
        )
    return "Random" if family == "random" else family.capitalize()


def _family_color(family: str) -> str:
    return FAMILY_COLORS.get(family, "accent")


def _ticks(rows: list[dict[str, str]], *, logx: bool, problem: str) -> tuple[str, str, str]:
    values = [_n(row) for row in rows]
    if logx:
        return (
            ",".join(str(value) for value in values),
            f"{values[0] * 0.85:.6g}",
            f"{values[-1] * 1.15:.6g}",
        )
    top = values[-1]
    step = 50 if problem == "sc1p" else 4
    ticks = list(range(0, top + 1, step))
    if ticks[-1] != top:
        ticks.append(top)
    return ",".join(str(value) for value in ticks), "0", f"{top * 1.05:.6g}"


def _plot(
    title: str,
    rows: list[dict[str, str]],
    color: str,
    *,
    multiple: bool,
) -> list[str]:
    label = title if multiple else "total"
    return [
        "\\addplot+[",
        f"  color={color}, mark=*, thick, mark size=1.6pt,",
        "  error bars/.cd, y dir=both, y explicit,",
        "  error bar style={black!45}, error mark options={rotate=90, mark size=1.4pt},",
        "] table[",
        "  col sep=comma,",
        "  x=n, y=wall_median_s,",
        "  y error plus=wall_err_plus_s,",
        "  y error minus=wall_err_minus_s,",
        "] {" + rows[0]["csv"] + "};",
        f"\\addlegendentry{{{label}}}",
    ]


def _figure(
    problem: str,
    families: dict[str, list[tuple[str, list[dict[str, str]]]]],
    *,
    logx: bool,
    logy: bool,
    label: str,
) -> str:
    order = {name: index for index, name in enumerate(("random_sat", "random"))}
    names = sorted(families, key=lambda name: order.get(name, 99))
    entries = [
        (_family_title(problem, family), families[family][0][1], _family_color(family))
        for family in names
    ]
    ticks, xmin, xmax = _ticks(entries[0][1], logx=logx, problem=problem)
    xmode = "log" if logx else "normal"
    ymode = "log" if logy else "normal"
    multiple = len(entries) > 1
    lines = [
        "% Requires in the preamble:",
        "% \\usepackage{pgfplots}",
        "% \\pgfplotsset{compat=1.18}",
        "\\providecolor{accent}{HTML}{355C7D}",
        "\\providecolor{okg}{HTML}{2E8B57}",
        "\\providecolor{brk}{HTML}{B04A5A}",
        "\\begin{figure}[htbp]",
        "\\centering",
        "\\begin{tikzpicture}",
        "\\begin{axis}[",
        "  width=0.82\\linewidth, height=0.46\\linewidth, scale only axis,",
        "  axis lines=left, axis line style={black!55},",
        "  tick style={black!55}, tick align=outside,",
        "  label style={font=\\small}, tick label style={font=\\scriptsize},",
        "  ylabel={median wall time (s)}, xlabel={columns $n$},",
        f"  xmode={xmode}, ymode={ymode},",
        f"  xtick={{{ticks}}}, xticklabels={{{ticks}}},",
        f"  xmin={xmin}, xmax={xmax},",
        *(["  ymin=0,"] if not logy else []),
        "  unbounded coords=jump,",
        "  grid=major, grid style={draw=black!10},",
        "  legend style={font=\\small, draw=none, fill=none,",
        "    at={(0.02,0.98)}, anchor=north west, legend cell align=left},",
        "]",
    ]
    for title, rows, color in entries:
        lines.extend(_plot(title, rows, color, multiple=multiple))
    lines.extend(
        [
            "\\end{axis}",
            "\\end{tikzpicture}",
            (
                f"\\caption{{{problem.upper()} scaling. X-axis is the matrix size $n$. "
                "Points are median wall times; bars are interquartile ranges.}"
            ),
            f"\\label{{{label}}}",
            "\\end{figure}",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate pgfplots scaling figures.")
    parser.add_argument("--csv-dir", type=Path, default=Path("benchmarks/results/csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("benchmarks/figures"))
    parser.add_argument("--problem", choices=("sc1p", "scbm"), required=True)
    parser.add_argument(
        "--csv-prefix",
        default="../results/csv/",
        help="path prefix written in the .tex files, relative to the .tex location",
    )
    args = parser.parse_args(argv)

    files = sorted(args.csv_dir.glob(f"{args.problem}-*.csv"))
    if not files:
        raise SystemExit(f"no CSV files for {args.problem} in {args.csv_dir}")
    families: dict[str, list[tuple[str, list[dict[str, str]]]]] = {}
    for path in files:
        parts = path.stem.split("-", 2)
        if len(parts) != 3:
            continue
        _, solver, family = parts
        if family not in FAMILY_COLORS:
            continue
        rows = _read(path)
        rows = [{**row, "csv": f"{args.csv_prefix}{path.name}"} for row in rows]
        families.setdefault(family, []).append((solver, rows))
    if not families:
        raise SystemExit("CSV names must be <problem>-<solver>-<family>.csv")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for mode, logx, logy in (
        ("loglog", True, True),
        ("semilog", False, True),
        ("linear", False, False),
    ):
        path = args.output_dir / f"{args.problem}-{mode}.tex"
        path.write_text(
            _figure(
                args.problem,
                families,
                logx=logx,
                logy=logy,
                label=f"fig:{args.problem}-{mode}",
            )
        )
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
