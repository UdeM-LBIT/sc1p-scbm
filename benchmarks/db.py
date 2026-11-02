"""Build the DuckDB database from raw benchmark Parquet files.

The database materialises only the raw tables. Medians, means, IQRs, solved
fractions, and every other derived statistic are computed by query, never
stored here.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

TABLES = ("batches", "instances", "runs", "repeats", "measurements")


def _quote(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def build_database(results_dir: Path, database: Path) -> duckdb.DuckDBPyConnection:
    parquet = results_dir / "parquet"
    if not any(parquet.glob("*/*.parquet")):
        raise SystemExit(f"no raw Parquet batches under {parquet}")
    database.parent.mkdir(parents=True, exist_ok=True)
    database.unlink(missing_ok=True)
    connection = duckdb.connect(str(database))
    for table in TABLES:
        pattern = _quote(parquet / "*" / f"{table}.parquet")
        connection.execute(
            f"CREATE OR REPLACE TABLE {table} AS "
            f"SELECT * FROM read_parquet('{pattern}', union_by_name = true)"
        )
    connection.execute("CREATE INDEX IF NOT EXISTS runs_run_id ON runs(run_id)")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS runs_group ON runs(problem, solver, family, n)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS measurements_run ON measurements(run_id)"
    )
    return connection


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the raw DuckDB catalog.")
    parser.add_argument("--results-dir", type=Path, default=Path("benchmarks/results"))
    parser.add_argument("--database", type=Path, default=Path("benchmarks/results/bench.duckdb"))
    args = parser.parse_args(argv)

    connection = build_database(args.results_dir, args.database)
    for table in TABLES:
        count = connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count}")
    connection.close()
    print(f"wrote {args.database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
