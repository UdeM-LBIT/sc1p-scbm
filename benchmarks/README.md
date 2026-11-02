# Benchmarks

Benchmark pipeline for SC1P and SCBM: raw Parquet batches, DuckDB
statistics, and pgfplots figures. The results are not stored in the
repository; the commands in [Run](#run) regenerate them.

```
benchmarks/run.py    -> Parquet raw batch
benchmarks/db.py     -> DuckDB raw tables loaded from the Parquet
benchmarks/report.py -> DuckDB metrics -> CSV
benchmarks/latex.py  -> pgfplots .tex reading the CSV
```

No derived statistic is stored. The database contains only the raw tables;
medians, IQR, means, errors and solved fractions are computed by `report.py` on
demand.

## Raw Parquet

Every batch gets an immutable directory:

```
benchmarks/results/parquet/<batch_id>/
    batches.parquet
    instances.parquet
    runs.parquet
    repeats.parquet
    measurements.parquet
```

| Table | Grain | Contents |
|---|---|---|
| `batches` | one row per invocation | CLI arguments, environment, CPU, package/git/lock hashes, git diff, timeout/cutoff, adaptive-stop markers |
| `instances` | one row per planned matrix | family, `n`, `m`, seed, full flat ternary matrix, matrix sha256, generator JSON including the witness order for satisfiable instances |
| `runs` | one row per (instance, solver) | outcome (`ok`/`timeout`/`error`/`skipped`), skip reason, traceback, satisfiable/objective, final permutation, verification, formula stats and formula hash, solver config, request timestamps, elapsed/cutoff/exit code |
| `repeats` | one row per repetition | per-repeat satisfiable/objective/permutation/verification and full solver statistics JSON |
| `measurements` | one row per (run, repeat, kind) | integer nanoseconds for `wall`, `build`, `solve`, `decode`, `total` |

Planned instances skipped by the adaptive cutoff still get `runs` rows with
`outcome='skipped'`, so denominators remain the full planned batch.

## DuckDB catalog

```bash
uv run --all-extras --group bench python benchmarks/db.py
```

This creates `benchmarks/results/bench.duckdb` with the raw tables `batches`,
`instances`, `runs`, `repeats`, `measurements`, loaded from
`benchmarks/results/parquet/*/`. No derived table, view, or aggregate is
stored.

## Metrics and CSV

```bash
uv run --all-extras --group bench python benchmarks/report.py --problem sc1p
```

`report.py` computes, from raw measurements:

- planned, attempted, solved, timeouts, errors, skipped;
- solved fraction over planned and over attempted;
- wall-time median, Q1, Q3, IQR, mean, standard deviation, min, max;
- build/solve/decode medians;
- unaccounted wall time (`wall - total`), the solver teardown residual.

Two-stage aggregation: median over repeats per run, then statistic over
instances. Outputs:

```
benchmarks/results/csv/stats-<problem>.csv      # all groups
benchmarks/results/csv/<problem>-<solver>-<family>.csv
```

Timeouts and skipped runs are excluded from timing statistics, never from the
solved/attempted/planned denominators. `nan` marks missing timing points for
pgfplots.

## LaTeX figures

```bash
uv run --all-extras --group bench python benchmarks/latex.py --problem sc1p
```

Outputs `benchmarks/figures/<problem>-loglog.tex`,
`benchmarks/figures/<problem>-semilog.tex`, and
`benchmarks/figures/<problem>-linear.tex`. Each is a single `axis` with one
median wall-time curve per family and interquartile error bars. SAT and UNSAT
share the SC1P axis; the SCBM figure uses `m=n`. The x-axis is always the matrix size
`n`; CSV paths are relative to the `.tex` location (`--csv-prefix`).

The generated files can be `\input` in any document that loads `pgfplots`
with `compat=1.18`. The paper uses the `-linear`
variant; the log variants remain available for diagnostics. The generator
uses the paper palette (`accent`, `okg`, `brk`), with `\providecolor`
fallbacks for standalone compilation.

## Run

Instance `i` of size `n` uses the seed `base + 1_000_003 * n + 97 * i`, where
`base` is `--seed`. The matrices therefore depend only on `--seed`, `n`, `i`
and `m`, not on the batch they belong to. All batches of the paper used the
seed below; these commands regenerate them.

```bash
uv sync --all-extras --group bench
bench() {
  uv run --all-extras --group bench python -u benchmarks/run.py \
    --seed 7416173917520333053 "$@"
}

# SC1P, satisfiable and UNSAT random instances, m = n
bench --problem sc1p --families random_sat --instances 100 \
  --sizes 10 20 30 40 50 75 100 150 200 250 300 400
bench --problem sc1p --families random --instances 100 \
  --sizes 10 20 30 40 50 75 100 150 200 250 300 400

# SCBM, m = n: 1000 instances for n <= 12, 100 for n = 13, 14
bench --problem scbm --sizes 4 5 6 7 8 9 10 11 12 --instances 1000
bench --problem scbm --sizes 13 14 --instances 100

# SCBM: rerun the instances that timed out at 60 s, with a 300 s cap
bench --problem scbm --sizes 13 --instances 100 --indices 39 --timeout 300
bench --problem scbm --sizes 14 --instances 100 \
  --indices 2 37 43 48 49 55 61 66 89 --timeout 300

# Supplementary sweeps over m
for r in 0.5 1 2 4 8; do
  bench --problem sc1p --families random_sat --sizes 100 --instances 100 --rows-ratio $r
done
for r in 0.5 1 1.5 2 2.5 3 3.5 4; do
  bench --problem scbm --sizes 10 --instances 20 --rows-ratio $r
done
```

`--rows-ratio r` sets `m = round(r * n)` and defaults to `1`. The default
family is `random`; `random_sat` builds a satisfiable matrix and shuffles its
columns. The default timeout is 60 s.

Each run writes a new batch id. `--results-dir` and `--batch-id` override the
location and identifier. Existing batch directories are never overwritten.

`-u` keeps stdout/stderr unbuffered. `tqdm` draws a live bar on a terminal;
redirected runs get plain `progress` lines every 10% and a timestamped log at
`benchmarks/results/<batch_id>.log`, readable with `tail -f`.

## Methodology

- Families: `random` (uniform ternary, mostly UNSAT at large `n`) and
  `random_sat` (satisfiable by construction, then shuffled columns).
- `m = n` in the main experiments of the paper; the supplementary sweeps vary
  `m` for a fixed `n`.
- Same matrix batch for every solver and family.
- Deterministic seed per instance, matrix and sha256 stored.
- Warmup before timing; per-repeat timings stored, not collapsed.
- One process per solve, per-instance cutoff, adaptive stop after
  `--timeout-stop` timeouts (default 3); skipped rows are explicit.
- One CPU: first available CPU by default, children inherit affinity, numerical
  library threads forced to one. `--pin-cpu N`, `--no-pin`.
- Default 100 instances per size and family.

The construction/step split matters for SC1P: `Φ(M)` construction is `O(n³ +
mn²)` and dominates at the tested sizes, so the wall curve is not a pure
SAT-search curve. SC1P is NP-complete, so the observed growth is an empirical
trend on random instances, not a complexity claim. The SCBM running time grows
exponentially in the tested range.

See [Benchmarking Solvers, SAT-style](https://ceur-ws.org/Vol-1974/RP3.pdf),
[MaxSAT Evaluation](https://maxsat-evaluations.github.io/2026/tracks.html), and
[pyperf](https://pyperf.readthedocs.io/en/latest/run_benchmark.html) for the
large-batch, per-instance-cutoff, distribution-first conventions. Parquet
format: <https://parquet.apache.org/>.
