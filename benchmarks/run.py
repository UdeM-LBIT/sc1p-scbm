"""Batch benchmarks for SC1P and SCBM.

Raw results are written as Parquet tables under
``benchmarks/results/parquet/<batch_id>/``:

- ``batches.parquet``: one row per invocation (arguments, environment, git state);
- ``instances.parquet``: one row per planned matrix, including the full matrix;
- ``runs.parquet``: one row per (instance, solver), including skipped runs;
- ``repeats.parquet``: one row per measured repetition and its result;
- ``measurements.parquet``: one row per (run, repeat, timing kind).

No derived statistics are stored. DuckDB computes medians, IQR, solved
fractions, etc. from these tables.

Example:
    uv run --all-extras --group bench python -u benchmarks/run.py --problem sc1p
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import platform
import random
import secrets
import subprocess
import sys
import time
import traceback
import uuid
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from tqdm import tqdm

import sc1p
import scbm
from schema import (
    BATCH_SCHEMA,
    INSTANCE_SCHEMA,
    MEASUREMENT_SCHEMA,
    REPEAT_SCHEMA,
    RUN_SCHEMA,
    SCHEMA_VERSION,
    instance_id,
    run_id,
    write_parquet,
)

DEFAULT_SIZES = {
    "sc1p": (10, 20, 30, 40, 50, 75, 100, 150),
    "scbm": (4, 6, 8, 10, 12, 14, 16, 18, 20, 24, 30),
}
DEFAULT_SOLVERS = {"sc1p": ("sat",), "scbm": ("maxsat",)}
FAMILIES = ("random", "random_sat")
WARM_MATRIX = [[1, 0, 1], [0, 1, 1], [1, 1, 0]]


def _version(package: str) -> str | None:
    try:
        return version(package)
    except PackageNotFoundError:
        return None


def _sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _git_state() -> dict:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, errors="replace", check=True
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, errors="replace", check=True
        ).stdout
        diff = subprocess.run(
            ["git", "diff"], capture_output=True, text=True, errors="replace", check=True
        ).stdout
        cached = subprocess.run(
            ["git", "diff", "--cached"], capture_output=True, text=True, errors="replace", check=True
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return {"commit": None, "dirty": None, "diff": None, "diff_sha256": None}
    full_diff = diff + cached
    return {
        "commit": commit,
        "dirty": bool(status),
        "diff": full_diff,
        "diff_sha256": hashlib.sha256(full_diff.encode()).hexdigest(),
    }


def _cpu_model() -> str | None:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or None


def _environment() -> dict:
    return {
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "kernel": platform.release(),
        "libc": list(platform.libc_ver()),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_model": _cpu_model(),
        "cpu_count": os.cpu_count(),
        "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "locale": list(__import__("locale").getlocale()),
        "timezone": list(time.tzname),
        "hash_randomization": sys.flags.hash_randomization,
        "thread_env": {
            key: os.environ.get(key)
            for key in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
        "sc1p_version": _version("sc1p"),
        "scbm_version": _version("scbm"),
        "python_sat_version": _version("python-sat"),
        "sowing_version": _version("sowing"),
        "uv_lock_sha256": _sha256_file(Path("uv.lock")),
        "pyproject_sha256": _sha256_file(Path("pyproject.toml")),
    }


def satisfiable_matrix(
    m: int, n: int, rng: random.Random, p0: float
) -> tuple[sc1p.Matrix, list[int]]:
    """Random matrix with a feasible SC1P order: each row has one contiguous 1-block."""
    order = list(range(n))
    rng.shuffle(order)
    matrix: sc1p.Matrix = []
    for _ in range(m):
        length = rng.randint(1, n)
        start = rng.randint(0, n - length)
        ones = set(order[start : start + length])
        matrix.append(
            [1 if column in ones else (0 if rng.random() < p0 else 2) for column in range(n)]
        )
    return matrix, order


def make_instance(
    family: str, m: int, n: int, rng: random.Random, p1: float, p0: float
) -> tuple[sc1p.Matrix, dict]:
    if family == "random_sat":
        matrix, order = satisfiable_matrix(m, n, rng, p0)
        return matrix, {"generator": "random_sat_matrix", "p0": p0, "order": order}
    matrix = sc1p.random_matrix(m, n, p1=p1, p0=p0, rng=rng)
    return matrix, {"generator": "random_matrix", "p1": p1, "p0": p0}


def call_solver(problem: str, solver: str, matrix: sc1p.Matrix):
    if problem == "sc1p":
        return sc1p.solve(matrix, solver=solver)
    return scbm.solve(matrix, solver=solver)


def _formula_hash(payload: object) -> str:
    return hashlib.sha256(repr(payload).encode()).hexdigest()


def _verify_sc1p(matrix: sc1p.Matrix, result) -> str:
    if not result.satisfiable:
        return "unchecked"
    assert result.permutation is not None
    return "solution_checked" if sc1p.verify(matrix, result.permutation) else "mismatch"


def _verify_scbm(matrix: sc1p.Matrix, result) -> str:
    cost = scbm.score.block_cost(matrix, result.permutation)
    return "solution_checked" if cost == result.cost else "mismatch"


def timed_sc1p_sat(matrix: sc1p.Matrix):
    """Time validation + Φ(M), SAT search, decoding, and capture solver statistics."""
    from pysat.solvers import Solver

    from sc1p.encoding.sat import extract_perm
    from sc1p.solvers.sat import build_phi

    started = time.perf_counter_ns()
    _, n = sc1p.validate_ternary(matrix)
    cnf = build_phi(matrix, n, symmetry_break=True)
    built = time.perf_counter_ns()
    with Solver(name="cadical153", bootstrap_with=cnf, use_timer=True) as solver:
        satisfiable = solver.solve()
        searched = time.perf_counter_ns()
        stats = dict(solver.accum_stats())
        stats.update(
            {
                "time": solver.time_accum(),
                "nof_vars": solver.nof_vars(),
                "nof_clauses": solver.nof_clauses(),
                "status": solver.get_status(),
            }
        )
        if not satisfiable:
            finished = time.perf_counter_ns()
            result = sc1p.SolveResult(False, None)
            return result, {
                "build": built - started,
                "solve": searched - built,
                "decode": finished - searched,
                "total": finished - started,
            }, stats, {
                "vars": cnf.nv,
                "clauses": len(cnf.clauses),
                "literals": sum(len(clause) for clause in cnf.clauses),
            }, _formula_hash(cnf.clauses), {
                "name": "cadical153",
                "use_timer": True,
                "symmetry_break": True,
            }
        model = solver.get_model()
        assert model is not None
        truth = {abs(value): value > 0 for value in model}
        permutation = extract_perm(truth, n, one_indexed=True)
        assert sc1p.verify(matrix, permutation)
    finished = time.perf_counter_ns()
    result = sc1p.SolveResult(True, permutation)
    return result, {
        "build": built - started,
        "solve": searched - built,
        "decode": finished - searched,
        "total": finished - started,
    }, stats, {
        "vars": cnf.nv,
        "clauses": len(cnf.clauses),
        "literals": sum(len(clause) for clause in cnf.clauses),
    }, _formula_hash(cnf.clauses), {
        "name": "cadical153",
        "use_timer": True,
        "symmetry_break": True,
    }


def timed_scbm_maxsat(matrix: sc1p.Matrix):
    """Time validation + Ψ(M), RC2, decoding, and capture solver statistics."""
    from pysat.examples.rc2 import RC2

    from sc1p.encoding.sat import extract_perm
    from scbm.exact.maxsat import build_psi
    from scbm.types import OptimizeResult

    started = time.perf_counter_ns()
    _, n = sc1p.validate_ternary(matrix)
    wcnf, constant = build_psi(matrix, n)
    built = time.perf_counter_ns()
    identity = list(range(n))
    formula = {
        "vars": wcnf.nv if wcnf is not None else None,
        "hard": len(wcnf.hard) if wcnf is not None else None,
        "soft": len(wcnf.soft) if wcnf is not None else None,
        "top": wcnf.topw if wcnf is not None else None,
        "constant": constant,
    }
    formula_hash = _formula_hash(
        None if wcnf is None else (wcnf.hard, wcnf.soft, wcnf.topw)
    )
    if wcnf is None:
        finished = time.perf_counter_ns()
        result = OptimizeResult(identity, constant)
        return result, {
            "build": built - started,
            "solve": 0,
            "decode": 0,
            "total": finished - started,
        }, {}, formula, formula_hash, {"name": "rc2", "active_rows": False}
    with RC2(wcnf) as rc2:
        model = rc2.compute()
        cost = rc2.cost
        searched = time.perf_counter_ns()
        stats = dict(rc2.oracle.accum_stats())
        stats.update(
            {
                "oracle_time": rc2.oracle_time(),
                "nof_vars": rc2.oracle.nof_vars(),
                "nof_clauses": rc2.oracle.nof_clauses(),
                "cost": cost,
                "solver": rc2.solver,
            }
        )
        if model is None:
            finished = time.perf_counter_ns()
            result = OptimizeResult(identity, scbm.score.block_cost(matrix, identity))
            return result, {
                "build": built - started,
                "solve": searched - built,
                "decode": finished - searched,
                "total": finished - started,
            }, stats, formula, formula_hash, {
                "name": "rc2",
                "oracle": rc2.solver,
                "active_rows": True,
            }
        truth = {abs(value): value > 0 for value in model}
        permutation = extract_perm(truth, n, one_indexed=True)
        assert scbm.score.block_cost(matrix, permutation) == cost
    finished = time.perf_counter_ns()
    result = OptimizeResult(permutation, cost)
    return result, {
        "build": built - started,
        "solve": searched - built,
        "decode": finished - searched,
        "total": finished - started,
    }, stats, formula, formula_hash, {
        "name": "rc2",
        "oracle": rc2.solver,
        "active_rows": True,
    }


def timed_solver(problem: str, solver: str, matrix: sc1p.Matrix):
    if problem == "sc1p" and solver == "sat":
        return timed_sc1p_sat(matrix)
    if problem == "scbm" and solver == "maxsat":
        return timed_scbm_maxsat(matrix)
    started = time.perf_counter_ns()
    result = call_solver(problem, solver, matrix)
    finished = time.perf_counter_ns()
    return result, {"total": finished - started}, {}, None, None, {}


def _worker(connection, problem: str, solver: str, matrix: sc1p.Matrix, repeat: int, warmup: int) -> None:
    try:
        for _ in range(warmup):
            call_solver(problem, solver, WARM_MATRIX)
        times: list[int] = []
        components: list[dict[str, int]] = []
        repeats: list[dict] = []
        formula_stats = formula_sha = solver_config = None
        result = None
        for _ in range(repeat):
            started = time.perf_counter_ns()
            result, timings, stats, formula, sha, config = timed_solver(
                problem, solver, matrix
            )
            times.append(time.perf_counter_ns() - started)
            components.append(timings)
            formula_stats, formula_sha, solver_config = formula, sha, config
            if problem == "sc1p":
                repeats.append(
                    {
                        "satisfiable": result.satisfiable,
                        "objective": None,
                        "permutation": result.permutation,
                        "verification": _verify_sc1p(matrix, result),
                    }
                )
            else:
                repeats.append(
                    {
                        "satisfiable": None,
                        "objective": result.cost,
                        "permutation": result.permutation,
                        "verification": _verify_scbm(matrix, result),
                    }
                )
            repeats[-1]["solver_stats"] = stats
        connection.send(
            {
                "times": times,
                "components": components,
                "repeats": repeats,
                "result": result,
                "formula_stats": formula_stats,
                "formula_sha256": formula_sha,
                "solver_config": solver_config,
            }
        )
    except BaseException:  # noqa: BLE001 - report every worker failure
        connection.send({"error": traceback.format_exc()})
    finally:
        connection.close()


def _process_context():
    try:
        return multiprocessing.get_context("fork")
    except ValueError:
        return multiprocessing.get_context()


def _pin_one_cpu(requested: int | None, disabled: bool) -> int | None:
    if disabled:
        return None
    if not hasattr(os, "sched_setaffinity"):
        print("warning: CPU affinity is not available on this platform", file=sys.stderr)
        return None
    allowed = sorted(os.sched_getaffinity(0))
    if not allowed:
        print("warning: no CPU is available for affinity", file=sys.stderr)
        return None
    cpu = allowed[0] if requested is None else requested
    if cpu not in allowed:
        print(f"warning: CPU {cpu} is not available; pinning to {allowed[0]}", file=sys.stderr)
        cpu = allowed[0]
    try:
        os.sched_setaffinity(0, {cpu})
    except OSError as exc:
        print(f"warning: cannot pin to CPU {cpu}: {exc}", file=sys.stderr)
        return None
    return cpu


def run_instance(
    context,
    *,
    batch_id: str,
    problem: str,
    solver: str,
    family: str,
    n: int,
    m: int,
    index: int,
    seed: int,
    matrix: sc1p.Matrix,
    timeout: float,
    repeat: int,
    warmup: int,
) -> dict:
    key = instance_id(batch_id, problem, family, n, m, index)
    identifier = run_id(batch_id, key, solver)
    deadline_ns = int((timeout * max(1, repeat) + 1.0) * 1_000_000_000)
    parent, child = context.Pipe(duplex=False)
    process = context.Process(
        target=_worker, args=(child, problem, solver, matrix, repeat, warmup)
    )
    started_epoch_ms = time.time_ns() // 1_000_000
    started = time.perf_counter_ns()
    process.start()
    child.close()
    payload = None
    try:
        if not parent.poll(deadline_ns / 1_000_000_000):
            process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join()
            elapsed = time.perf_counter_ns() - started
            return {
                "run_id": identifier,
                "instance_id": key,
                "outcome": "timeout",
                "skip_reason": None,
                "error": None,
                "elapsed_ns": elapsed,
                "cutoff_ns": deadline_ns,
                "exitcode": process.exitcode,
                "started_epoch_ms": started_epoch_ms,
                "finished_epoch_ms": time.time_ns() // 1_000_000,
                "payload": None,
            }
        payload = parent.recv()
    except EOFError:
        payload = {"error": "worker exited without a result"}
    finally:
        parent.close()
        process.join(5)
        if process.is_alive():
            process.terminate()
            process.join()
    elapsed = time.perf_counter_ns() - started
    finished = time.time_ns() // 1_000_000
    if "error" in payload:
        return {
            "run_id": identifier,
            "instance_id": key,
            "outcome": "error",
            "skip_reason": None,
            "error": payload["error"],
            "elapsed_ns": elapsed,
            "cutoff_ns": deadline_ns,
            "exitcode": process.exitcode,
            "started_epoch_ms": started_epoch_ms,
            "finished_epoch_ms": finished,
            "payload": None,
        }
    return {
        "run_id": identifier,
        "instance_id": key,
        "outcome": "ok",
        "skip_reason": None,
        "error": None,
        "elapsed_ns": elapsed,
        "cutoff_ns": deadline_ns,
        "exitcode": process.exitcode,
        "started_epoch_ms": started_epoch_ms,
        "finished_epoch_ms": finished,
        "payload": payload,
    }


def _run_row(result: dict, *, batch_id: str, problem: str, solver: str, family: str, n: int, m: int, index: int, seed: int) -> dict:
    payload = result["payload"]
    satisfiable = objective = permutation = verification = None
    formula_stats = formula_sha = solver_config = None
    if payload is not None:
        last = payload["repeats"][-1]
        satisfiable = last["satisfiable"]
        objective = last["objective"]
        permutation = last["permutation"]
        verification = last["verification"]
        formula_stats = json.dumps(payload.get("formula_stats"))
        formula_sha = payload.get("formula_sha256")
        solver_config = json.dumps(payload.get("solver_config"))
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": result["run_id"],
        "batch_id": batch_id,
        "instance_id": result["instance_id"],
        "problem": problem,
        "solver": solver,
        "family": family,
        "n": n,
        "m": m,
        "instance": index,
        "seed": seed,
        "outcome": result["outcome"],
        "skip_reason": result["skip_reason"],
        "error": result["error"],
        "satisfiable": satisfiable,
        "objective": objective,
        "permutation": permutation,
        "verification": verification,
        "formula_stats_json": formula_stats,
        "formula_sha256": formula_sha,
        "solver_config_json": solver_config,
        "started_epoch_ms": result["started_epoch_ms"],
        "finished_epoch_ms": result["finished_epoch_ms"],
        "elapsed_ns": result["elapsed_ns"],
        "cutoff_ns": result["cutoff_ns"],
        "exitcode": result["exitcode"],
    }


def _repeat_rows(result: dict) -> list[dict]:
    payload = result["payload"]
    if payload is None:
        return []
    rows = []
    for repeat, last in enumerate(payload["repeats"]):
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "run_id": result["run_id"],
                "repeat": repeat,
                "satisfiable": last["satisfiable"],
                "objective": last["objective"],
                "permutation": last["permutation"],
                "verification": last["verification"],
                "solver_stats_json": json.dumps(last["solver_stats"]),
            }
        )
    return rows


def _measurement_rows(result: dict) -> list[dict]:
    payload = result["payload"]
    if payload is None:
        return []
    rows = []
    for repeat, (wall, components) in enumerate(
        zip(payload["times"], payload["components"])
    ):
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "run_id": result["run_id"],
                "repeat": repeat,
                "kind": "wall",
                "value_ns": wall,
            }
        )
        for kind, value in components.items():
            rows.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "run_id": result["run_id"],
                    "repeat": repeat,
                    "kind": kind,
                    "value_ns": value,
                }
            )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch-benchmark SC1P or SCBM.")
    parser.add_argument("--problem", choices=("sc1p", "scbm"), required=True)
    parser.add_argument("--sizes", type=int, nargs="+", default=None)
    parser.add_argument("--instances", type=int, default=100)
    parser.add_argument(
        "--indices",
        type=int,
        nargs="+",
        default=None,
        help="rerun only these instance indices; overrides the 0..instances-1 loop",
    )
    parser.add_argument("--families", nargs="+", choices=FAMILIES, default=["random"])
    parser.add_argument("--solver", nargs="+", default=None)
    parser.add_argument("--rows-ratio", type=float, default=None)
    parser.add_argument("--p1", type=float, default=0.3)
    parser.add_argument("--p0", type=float, default=0.5)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--timeout-stop", type=int, default=3)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20261101)
    parser.add_argument(
        "--system-random",
        action="store_true",
        help="draw matrix cells from os entropy instead of a seeded Mersenne Twister",
    )
    parser.add_argument("--pin-cpu", type=int, default=None)
    parser.add_argument("--no-pin", action="store_true")
    parser.add_argument("--results-dir", type=Path, default=Path("benchmarks/results"))
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--log", type=Path, default=None)
    args = parser.parse_args(argv)

    for variable in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ.setdefault(variable, "1")

    sizes = sorted(set(args.sizes or DEFAULT_SIZES[args.problem]))
    solvers = args.solver or list(DEFAULT_SOLVERS[args.problem])
    rows_ratio = args.rows_ratio if args.rows_ratio is not None else 1.0
    if rows_ratio <= 0:
        parser.error("--rows-ratio must be positive")
    available = sc1p.available() if args.problem == "sc1p" else scbm.available()
    missing = [solver for solver in solvers if solver not in available]
    if missing:
        parser.error(f"solvers not available: {', '.join(missing)}; available: {', '.join(available)}")
    if args.instances < 1 or any(n < 1 for n in sizes):
        parser.error("--instances and every size must be positive")
    indices = sorted(set(args.indices)) if args.indices else list(range(args.instances))
    if any(index < 0 for index in indices):
        parser.error("--indices must be non-negative")
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    if args.timeout_stop < 0:
        parser.error("--timeout-stop must be non-negative")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    started_epoch_ms = time.time_ns() // 1_000_000
    base_seed = secrets.randbits(63) if args.system_random else args.seed
    batch_id = args.batch_id or (
        f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{args.problem}-{uuid.uuid4().hex[:8]}"
    )
    batch_dir = args.results_dir / "parquet" / batch_id
    if batch_dir.exists():
        parser.error(f"batch directory already exists: {batch_dir}")
    batch_dir.mkdir(parents=True)
    log_path = args.log or args.results_dir / f"{batch_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("w")

    def log(message: str, *, echo: bool = True) -> None:
        line = f"{datetime.now(UTC).strftime('%H:%M:%S')} {message}"
        log_handle.write(line + "\n")
        log_handle.flush()
        if echo:
            print(message, file=sys.stderr, flush=True)

    actual_cpu = _pin_one_cpu(args.pin_cpu, args.no_pin)
    if actual_cpu is not None:
        log(f"pinned to CPU {actual_cpu}", echo=False)

    environment = _environment()
    git = _git_state()
    instances: list[dict] = []
    runs: list[dict] = []
    repeats: list[dict] = []
    measurements: list[dict] = []
    stopped: list[dict] = []
    blocked: set[tuple[str, str]] = set()
    deadline_s = args.timeout * max(1, args.repeat) + 1.0

    batch_row = {
        "schema_version": SCHEMA_VERSION,
        "batch_id": batch_id,
        "problem": args.problem,
        "started_epoch_ms": started_epoch_ms,
        "finished_epoch_ms": None,
        "args_json": json.dumps(vars(args), default=str),
        "environment_json": json.dumps(environment, default=str),
        "sizes": sizes,
        "instances": len(indices),
        "families": args.families,
        "solvers": solvers,
        "rows_ratio": rows_ratio,
        "p1": args.p1,
        "p0": args.p0,
        "timeout_s": args.timeout,
        "deadline_s": deadline_s,
        "timeout_stop": args.timeout_stop,
        "repeat": args.repeat,
        "warmup": args.warmup,
        "base_seed": base_seed,
        "pin_cpu": actual_cpu,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cpu_model": environment["cpu_model"],
        "cpu_count": os.cpu_count(),
        "sc1p_version": _version("sc1p"),
        "scbm_version": _version("scbm"),
        "python_sat_version": _version("python-sat"),
        "uv_lock_sha256": environment["uv_lock_sha256"],
        "pyproject_sha256": environment["pyproject_sha256"],
        "git_commit": git["commit"],
        "git_dirty": git["dirty"],
        "git_diff_sha256": git["diff_sha256"],
        "git_diff": git["diff"],
        "stopped": stopped,
    }

    def write_checkpoint(final: bool = False) -> None:
        if final:
            batch_row["finished_epoch_ms"] = time.time_ns() // 1_000_000
        write_parquet(batch_dir / "batches.parquet", [batch_row], BATCH_SCHEMA)
        write_parquet(batch_dir / "instances.parquet", instances, INSTANCE_SCHEMA)
        write_parquet(batch_dir / "runs.parquet", runs, RUN_SCHEMA)
        write_parquet(batch_dir / "repeats.parquet", repeats, REPEAT_SCHEMA)
        write_parquet(batch_dir / "measurements.parquet", measurements, MEASUREMENT_SCHEMA)

    log(
        f"start {batch_id} {args.problem} sizes={sizes} instances={len(indices)} "
        f"families={args.families} solvers={solvers} timeout={args.timeout}s "
        f"pin_cpu={actual_cpu} base_seed={base_seed} dir={batch_dir}"
    )
    context = _process_context()
    try:
        for n in sizes:
            m = max(1, round(rows_ratio * n))
            for family in args.families:
                active = [solver for solver in solvers if (solver, family) not in blocked]
                timeouts = {solver: 0 for solver in active}
                bar = tqdm(
                    indices,
                    desc=f"{args.problem} n={n} {family}",
                    unit="matrix",
                    file=sys.stderr,
                    dynamic_ncols=True,
                    leave=False,
                    disable=None,
                )
                progress_every = max(1, len(indices) // 10)
                log(f"batch start {args.problem} n={n} m={m} family={family}")
                for index in bar:
                    seed = args.seed + 1_000_003 * n + 97 * index
                    rng = random.SystemRandom() if args.system_random else random.Random(seed)
                    matrix, generator = make_instance(
                        family, m, n, rng, args.p1, args.p0
                    )
                    flat = [cell for row in matrix for cell in row]
                    matrix_sha = hashlib.sha256(bytes(flat)).hexdigest()
                    key = instance_id(batch_id, args.problem, family, n, m, index)
                    instances.append(
                        {
                            "schema_version": SCHEMA_VERSION,
                            "batch_id": batch_id,
                            "instance_id": key,
                            "problem": args.problem,
                            "family": family,
                            "n": n,
                            "m": m,
                            "instance": index,
                            "seed": seed,
                            "generated": matrix is not None,
                            "matrix": flat,
                            "matrix_sha256": matrix_sha,
                            "generator_json": json.dumps(
                                {"family": family, "m": m, "n": n, "seed": seed, **(generator or {})}
                            ),
                        }
                    )
                    for solver in solvers:
                        if solver not in active:
                            runs.append(
                                {
                                    "schema_version": SCHEMA_VERSION,
                                    "run_id": run_id(batch_id, key, solver),
                                    "batch_id": batch_id,
                                    "instance_id": key,
                                    "problem": args.problem,
                                    "solver": solver,
                                    "family": family,
                                    "n": n,
                                    "m": m,
                                    "instance": index,
                                    "seed": seed,
                                    "outcome": "skipped",
                                    "skip_reason": "timeout_cutoff",
                                    "error": None,
                                    "satisfiable": None,
                                    "objective": None,
                                    "permutation": None,
                                    "verification": None,
                                    "formula_stats_json": None,
                                    "formula_sha256": None,
                                    "solver_config_json": None,
                                    "started_epoch_ms": None,
                                    "finished_epoch_ms": None,
                                    "elapsed_ns": None,
                                    "cutoff_ns": None,
                                    "exitcode": None,
                                }
                            )
                            continue
                        assert matrix is not None
                        raw = run_instance(
                            context,
                            batch_id=batch_id,
                            problem=args.problem,
                            solver=solver,
                            family=family,
                            n=n,
                            m=m,
                            index=index,
                            seed=seed,
                            matrix=matrix,
                            timeout=args.timeout,
                            repeat=args.repeat,
                            warmup=args.warmup,
                        )
                        runs.append(
                            _run_row(
                                raw,
                                batch_id=batch_id,
                                problem=args.problem,
                                solver=solver,
                                family=family,
                                n=n,
                                m=m,
                                index=index,
                                seed=seed,
                            )
                        )
                        repeats.extend(_repeat_rows(raw))
                        measurements.extend(_measurement_rows(raw))
                        if raw["outcome"] == "timeout":
                            bar.set_postfix_str(f"{solver}: timeout", refresh=False)
                            timeouts[solver] += 1
                            if args.timeout_stop and timeouts[solver] >= args.timeout_stop:
                                active.remove(solver)
                                blocked.add((solver, family))
                                stopped.append(
                                    {"solver": solver, "family": family, "n": n, "timeouts": timeouts[solver]}
                                )
                                message = (
                                    f"stopped {args.problem}/{solver}/{family} at n={n} "
                                    f"after {timeouts[solver]} timeouts; larger sizes skipped"
                                )
                                bar.write(message)
                                log(message, echo=False)
                        elif raw["payload"] is not None:
                            elapsed = raw["payload"]["times"][-1] / 1e9
                            bar.set_postfix_str(f"{solver}: {elapsed:.3g}s", refresh=False)
                        ordinal = indices.index(index) + 1
                        if ordinal % progress_every == 0 or ordinal == len(indices):
                            message = (
                                f"progress {args.problem} n={n} family={family} "
                                f"{ordinal}/{len(indices)} active={active}"
                            )
                            bar.write(message)
                            log(message, echo=False)
                bar.close()
                log(f"{args.problem} n={n} m={m} family={family}: {len(indices)} planned")
                write_checkpoint()
    except KeyboardInterrupt:
        log("interrupted; writing partial results", echo=True)
        write_checkpoint()
        return 130
    finally:
        log_handle.close()

    write_checkpoint(final=True)
    print(f"wrote raw Parquet batch {batch_dir} and log {log_path}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
