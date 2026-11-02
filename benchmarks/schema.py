"""Raw Parquet schemas for benchmark runs.

Only measured facts live here: batch configuration, generated matrices,
per-repeat outcomes/timings, and solver statistics. Medians, IQR, means and
solved fractions are computed later by DuckDB queries.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

SCHEMA_VERSION = 1

STOPPED = pa.list_(
    pa.struct(
        [
            pa.field("solver", pa.string()),
            pa.field("family", pa.string()),
            pa.field("n", pa.int32()),
            pa.field("timeouts", pa.int32()),
        ]
    )
)

BATCH_SCHEMA = pa.schema(
    [
        pa.field("schema_version", pa.int16()),
        pa.field("batch_id", pa.string()),
        pa.field("problem", pa.string()),
        pa.field("started_epoch_ms", pa.int64()),
        pa.field("finished_epoch_ms", pa.int64()),
        pa.field("args_json", pa.string()),
        pa.field("environment_json", pa.string()),
        pa.field("sizes", pa.list_(pa.int32())),
        pa.field("instances", pa.int32()),
        pa.field("families", pa.list_(pa.string())),
        pa.field("solvers", pa.list_(pa.string())),
        pa.field("rows_ratio", pa.float64()),
        pa.field("p1", pa.float64()),
        pa.field("p0", pa.float64()),
        pa.field("timeout_s", pa.float64()),
        pa.field("deadline_s", pa.float64()),
        pa.field("timeout_stop", pa.int32()),
        pa.field("repeat", pa.int32()),
        pa.field("warmup", pa.int32()),
        pa.field("base_seed", pa.int64()),
        pa.field("pin_cpu", pa.int32()),
        pa.field("python_version", pa.string()),
        pa.field("platform", pa.string()),
        pa.field("cpu_model", pa.string()),
        pa.field("cpu_count", pa.int32()),
        pa.field("sc1p_version", pa.string()),
        pa.field("scbm_version", pa.string()),
        pa.field("python_sat_version", pa.string()),
        pa.field("uv_lock_sha256", pa.string()),
        pa.field("pyproject_sha256", pa.string()),
        pa.field("git_commit", pa.string()),
        pa.field("git_dirty", pa.bool_()),
        pa.field("git_diff_sha256", pa.string()),
        pa.field("git_diff", pa.string()),
        pa.field("stopped", STOPPED),
    ]
)

INSTANCE_SCHEMA = pa.schema(
    [
        pa.field("schema_version", pa.int16()),
        pa.field("batch_id", pa.string()),
        pa.field("instance_id", pa.int64()),
        pa.field("problem", pa.string()),
        pa.field("family", pa.string()),
        pa.field("n", pa.int32()),
        pa.field("m", pa.int32()),
        pa.field("instance", pa.int32()),
        pa.field("seed", pa.int64()),
        pa.field("generated", pa.bool_()),
        pa.field("matrix", pa.list_(pa.int8())),
        pa.field("matrix_sha256", pa.string()),
        pa.field("generator_json", pa.string()),
    ]
)

RUN_SCHEMA = pa.schema(
    [
        pa.field("schema_version", pa.int16()),
        pa.field("run_id", pa.int64()),
        pa.field("batch_id", pa.string()),
        pa.field("instance_id", pa.int64()),
        pa.field("problem", pa.string()),
        pa.field("solver", pa.string()),
        pa.field("family", pa.string()),
        pa.field("n", pa.int32()),
        pa.field("m", pa.int32()),
        pa.field("instance", pa.int32()),
        pa.field("seed", pa.int64()),
        pa.field("outcome", pa.string()),
        pa.field("skip_reason", pa.string()),
        pa.field("error", pa.string()),
        pa.field("satisfiable", pa.bool_()),
        pa.field("objective", pa.int64()),
        pa.field("permutation", pa.list_(pa.int32())),
        pa.field("verification", pa.string()),
        pa.field("formula_stats_json", pa.string()),
        pa.field("formula_sha256", pa.string()),
        pa.field("solver_config_json", pa.string()),
        pa.field("started_epoch_ms", pa.int64()),
        pa.field("finished_epoch_ms", pa.int64()),
        pa.field("elapsed_ns", pa.int64()),
        pa.field("cutoff_ns", pa.int64()),
        pa.field("exitcode", pa.int32()),
    ]
)

REPEAT_SCHEMA = pa.schema(
    [
        pa.field("schema_version", pa.int16()),
        pa.field("run_id", pa.int64()),
        pa.field("repeat", pa.int32()),
        pa.field("satisfiable", pa.bool_()),
        pa.field("objective", pa.int64()),
        pa.field("permutation", pa.list_(pa.int32())),
        pa.field("verification", pa.string()),
        pa.field("solver_stats_json", pa.string()),
    ]
)

MEASUREMENT_SCHEMA = pa.schema(
    [
        pa.field("schema_version", pa.int16()),
        pa.field("run_id", pa.int64()),
        pa.field("repeat", pa.int32()),
        pa.field("kind", pa.string()),
        pa.field("value_ns", pa.int64()),
    ]
)


def _stable_id(*parts: object) -> int:
    text = "|".join(str(part) for part in parts)
    digest = hashlib.blake2b(text.encode(), digest_size=8).digest()
    return int.from_bytes(digest, "little") & 0x7FFF_FFFF_FFFF_FFFF


def instance_id(batch_id: str, problem: str, family: str, n: int, m: int, index: int) -> int:
    return _stable_id(batch_id, problem, family, n, m, index)


def run_id(batch_id: str, instance_key: int, solver: str) -> int:
    return _stable_id(batch_id, instance_key, solver)


def table(rows: list[dict], schema: pa.Schema) -> pa.Table:
    return pa.Table.from_pylist(rows, schema=schema)


def write_parquet(path: Path, rows: list[dict], schema: pa.Schema) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    pq.write_table(table(rows, schema), temporary, compression="zstd")
    temporary.replace(path)
