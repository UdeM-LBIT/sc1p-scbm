"""Compute benchmark statistics from the raw DuckDB catalog and export CSV.

All metrics are derived here from raw measurements; none are stored in the
database. The CSV files are the only input to the pgfplots generator.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from db import build_database

STATS_SQL = """
WITH chosen AS (
    SELECT problem, solver, family, n, m, batch_id
    FROM (
        SELECT r.problem, r.solver, r.family, r.n, r.m, b.batch_id,
               row_number() OVER (
                   PARTITION BY r.problem, r.solver, r.family, r.n, r.m
                   ORDER BY b.timeout_s DESC, b.started_epoch_ms DESC
               ) AS rank
        FROM runs r
        JOIN batches b USING (batch_id)
    )
    WHERE rank = 1
),
run_times AS (
    SELECT run_id,
           median(value_ns) FILTER (WHERE kind = 'wall') / 1e9 AS wall_s,
           median(value_ns) FILTER (WHERE kind = 'build') / 1e9 AS build_s,
           median(value_ns) FILTER (WHERE kind = 'solve') / 1e9 AS solve_s,
           median(value_ns) FILTER (WHERE kind = 'decode') / 1e9 AS decode_s,
           median(value_ns) FILTER (WHERE kind = 'total') / 1e9 AS total_s
    FROM measurements
    GROUP BY run_id
),
runs_x AS (
    SELECT r.*,
           b.timeout_s,
           b.deadline_s,
           b.repeat AS repeat_target,
           b.git_commit,
           t.wall_s,
           t.build_s,
           t.solve_s,
           t.decode_s,
           t.total_s,
           t.wall_s - t.total_s AS unaccounted_s,
           r.outcome = 'ok' AS is_solved
    FROM runs r
    JOIN chosen c
      ON c.problem = r.problem AND c.solver = r.solver
     AND c.family = r.family AND c.n = r.n AND c.m = r.m
    JOIN batches b ON b.batch_id = r.batch_id
    LEFT JOIN run_times t ON t.run_id = r.run_id
    WHERE r.batch_id = c.batch_id
),
grouped AS (
    SELECT problem, solver, family, n, m,
           count(*) AS planned,
           count(*) FILTER (WHERE outcome <> 'skipped') AS attempted,
           count(*) FILTER (WHERE outcome = 'ok') AS solved,
           count(*) FILTER (WHERE outcome = 'timeout') AS timeout_count,
           count(*) FILTER (WHERE outcome = 'error') AS errors,
           count(*) FILTER (WHERE outcome = 'skipped') AS skipped,
           median(wall_s) FILTER (WHERE is_solved) AS wall_median_s,
           quantile_cont(wall_s, 0.25) FILTER (WHERE is_solved) AS wall_q1_s,
           quantile_cont(wall_s, 0.75) FILTER (WHERE is_solved) AS wall_q3_s,
           avg(wall_s) FILTER (WHERE is_solved) AS wall_mean_s,
           stddev_samp(wall_s) FILTER (WHERE is_solved) AS wall_stdev_s,
           min(wall_s) FILTER (WHERE is_solved) AS wall_min_s,
           max(wall_s) FILTER (WHERE is_solved) AS wall_max_s,
           median(build_s) FILTER (WHERE is_solved) AS build_median_s,
           median(solve_s) FILTER (WHERE is_solved) AS solve_median_s,
           median(decode_s) FILTER (WHERE is_solved) AS decode_median_s,
           median(unaccounted_s) FILTER (WHERE is_solved) AS unaccounted_median_s
    FROM runs_x
    GROUP BY ALL
)
SELECT *,
       solved::DOUBLE / planned AS solved_fraction_planned,
       solved::DOUBLE / planned * 100 AS solved_percent,
       timeout_count::DOUBLE / planned AS timeout_fraction,
       skipped::DOUBLE / planned AS skipped_fraction,
       errors::DOUBLE / planned AS error_fraction,
       CASE WHEN attempted > 0 THEN solved::DOUBLE / attempted END AS solved_fraction_attempted,
       coalesce(wall_q3_s - wall_median_s, 0) AS wall_err_plus_s,
       coalesce(wall_median_s - wall_q1_s, 0) AS wall_err_minus_s
FROM grouped
ORDER BY problem, solver, family, m, n
"""


def _write_csv(path: Path, rows: list[tuple], description: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = [column[0] for column in description]
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(names)
        for row in rows:
            writer.writerow(["nan" if value is None else value for value in row])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export benchmark statistics to CSV.")
    parser.add_argument("--results-dir", type=Path, default=Path("benchmarks/results"))
    parser.add_argument("--database", type=Path, default=Path("benchmarks/results/bench.duckdb"))
    parser.add_argument("--output-dir", type=Path, default=Path("benchmarks/results/csv"))
    parser.add_argument("--problem", choices=("sc1p", "scbm"), default=None)
    parser.add_argument("--family", choices=("random", "random_sat"), default=None)
    args = parser.parse_args(argv)

    connection = build_database(args.results_dir, args.database)
    filters = []
    if args.problem:
        filters.append(f"problem = '{args.problem}'")
    if args.family:
        filters.append(f"family = '{args.family}'")
    where = f"WHERE {' AND '.join(filters)} " if filters else ""
    query = STATS_SQL.replace("ORDER BY problem", f"{where}ORDER BY problem")
    cursor = connection.execute(query)
    rows = cursor.fetchall()
    description = cursor.description
    names = [column[0] for column in description]

    stem = "-".join(part for part in (args.problem, args.family) if part) or "all"
    all_path = args.output_dir / f"stats-{stem}.csv"
    _write_csv(all_path, rows, description)
    print(all_path)

    indexes = {name: index for index, name in enumerate(names)}
    groups: dict[tuple[str, str, str, float | None], list[tuple]] = {}
    for row in rows:
        problem = row[indexes["problem"]]
        ratio = None
        if problem == "scbm":
            ratio = row[indexes["m"]] / row[indexes["n"]]
        key = (problem, row[indexes["solver"]], row[indexes["family"]], ratio)
        groups.setdefault(key, []).append(row)
    for (problem, solver, family, ratio), group in sorted(groups.items()):
        suffix = f"-r{ratio:g}" if ratio is not None else ""
        path = args.output_dir / f"{problem}-{solver}-{family}{suffix}.csv"
        _write_csv(path, group, description)
        print(path)

    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
