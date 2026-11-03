# sc1p-scbm

Exact SAT and MaxSAT solvers for the Sandwich Consecutive Ones Property (SC1P)
and Sandwich Consecutive-Block Minimization (SCBM) on ternary matrices. They
accompany the paper *Ordering genes to minimize segmental gains and losses in
synteny histories* (Laberge, Delabre, Gascon, El-Mabrouk). Both problems take
a ternary matrix `M ∈ {0, 1, X}^{m×n}`, stored with `X = 2`: one row per gain or loss
event, one column per gene family, `1` for a family involved in the event, `0`
for a family present on both sides of the event, and `X` for a family absent
from the event context.

- **SC1P** (Sandwich Consecutive Ones Property, decision): is there a common
  column order `π` in which, once the `X` entries of a row are deleted, its `1`
  entries are contiguous?
- **SCBM** (Sandwich Consecutive-Block Minimization, optimization): a *block*
  of a row is a substring without `0` that starts and ends with a `1`, and a
  *maximal block* is a block not included in a larger one. Write `b(M^π)` for
  the number of maximal blocks of `M^π`, and `SCBM(M) = min_π b(M^π)`. Rows
  without a `1` contribute zero. On an event matrix, `b(M^π) ≥ λ + γ`, and
  equality holds exactly when `M` has SC1P.

For a single-origin synteny tree, the Minimum Ordered Synteny History (MOSH)
problem reduces to SCBM on the tree's event matrix, and the decision version
DEMOSH reduces to SC1P.

The repository is a `uv` workspace of three packages. The two solvers work on
any ternary matrix and know nothing about genomes:

- `sc1p` builds the precedence CNF `Φ(M)` of the SAT section and solves it
  with CaDiCaL;
- `scbm` builds the weighted partial MaxSAT instance `Ψ(M)` of the precedence
  encoding and solves it with RC2;
- `synteny-tree` builds the event matrix of a synteny tree, to be passed to
  either solver.

## Install

```bash
uv sync --all-extras
```

or, with pip, `pip install ./packages/sc1p[sat] ./packages/scbm[sat]
./packages/synteny-tree`. The `sat` extra pulls in PySAT, and
`synteny-tree` depends on the [sowing](https://github.com/UdeM-LBIT/sowing)
tree library. Backends are imported on first use, so `scbm.score.block_cost`
needs neither.

## Usage

```python
import sc1p
import scbm

M = sc1p.sc1p_example()

sat, perm = sc1p.solve(M, solver="sat")  # one SC1P order, or (False, None)
orders = sc1p.solve_all(M)  # every SC1P order
sc1p.verify(M, perm)

perm, cost = scbm.solve(M, solver="maxsat")  # cost = b(M^π) = SCBM(M) at optimum
scbm.score.block_cost(M, perm)  # b(M^π) for any order
scbm.score.block_lower_bound(M)  # rows containing a 1; λ+γ on an event matrix

report = scbm.analyze(M)  # has_sc1p iff cost == block_lower_bound(M)
solutions = scbm.solve_all(M)  # every optimal order; backend enumeration
```

`solver="auto"` is the default: `sat` then `brute_force` for SC1P,
`maxsat` then `brute_force` for SCBM, whichever is installed first.

| Package | Backend       | Method                                                    |
| ------- | ------------- | --------------------------------------------------------- |
| `sc1p`  | `sat`         | precedence encoding `Φ(M)`, CaDiCaL                       |
| `sc1p`  | `brute_force` | enumeration of all `n!` orders                            |
| `scbm`  | `maxsat`      | precedence encoding `Ψ(M)`, RC2 (supplement Alg. S2)      |
| `scbm`  | `brute_force` | enumeration of all `n!` orders                            |

The MaxSAT backend counts every block in the weighted objective, including
constant contributions from trivial rows. The raw RC2 optimum equals the
returned total block cost; no lower bound or caller-side offset is added.
If `n ≤ 1` or there is no active row (`A = ∅`), `maxsat` returns the identity
order and its exact block cost without building a formula.

A new backend is a class with a `solve` method, registered under a name:

```python
from sc1p import SolveResult, register


@register("mine")
class MySolver:
    def solve(self, matrix) -> SolveResult: ...
    def solve_all(self, matrix) -> list[list[int]]: ...


sc1p.solve(M, solver="mine")
```

## Command line

Both commands print JSON.

```bash
sc1p '[[1,2,0],[0,1,2]]'                         # {"satisfiable": ..., "permutation": ...}
sc1p '[[1,2,0],[0,1,2]]' --all
scbm solve '[[1,0,1],[0,1,1],[1,1,0]]' --solver maxsat   # {"cost": 4, "permutation": ...}
scbm analyze '[[1,2,0],[0,1,2]]'
```

## Event matrices of synteny trees

`synteny_tree.event_matrix` builds the event matrix of a synteny tree
`⟨T, x⟩`, where `T` is a rooted sowing tree and `x` gives the synteny of
**every** node; contents of internal nodes are never inferred from the leaves.
As in the paper, the event matrix `M` is the loss matrix `M⁻` stacked on the
gain matrix `M⁺` (`loss_matrix`, `gain_matrix`), and the planted edge above
the root gains the content of the root.

```python
from sowing import Node
from synteny_tree import event_matrix
import sc1p
import scbm

tree = Node("ρ").add(Node("u").add(Node("v")).add(Node("w")))
x = {
    "ρ": frozenset({0, 1, 2}),
    "u": frozenset({0, 1}),
    "v": frozenset({0}),
    "w": frozenset({0, 1}),
}
M = event_matrix(tree, x, families=(0, 1, 2))
sc1p.solve(M)  # DEMOSH: is there an order with λ + γ segmental events?
scbm.solve(M)  # MOSH: an order minimizing the number of segmental events
```

`event_matrix` requires a single-origin tree, in which every family is gained
on exactly one edge; for other trees, `occurrence_expansion` builds the
occurrence-expanded tree of the paper first. See
[`packages/synteny-tree`](packages/synteny-tree) for the other input formats
(Newick strings, contents stored on the nodes, labeling functions).

## InOutParsimony histories and observed leaf orders

`scbm history` reads one or more single-origin histories from an
InOutParsimony `solutions show` NHX output. It reconstructs each event matrix,
compares the histories, and returns a JSON report. For example:

```bash
scbm history examples/crispr-class1/crispr-class1-out-lo20-le10-go1.out.nhx \
  --loss-open 20 --loss-ext 10 --gain-open 1
```

The event cost is `open × number of blocks + extension × number of genes`:
this follows InOutParsimony's `open + extension × size` convention for each
segment. The JSON reports both the cost recorded in the NHX and its recomputed
InOutParsimony cost, along with the optimized segment cost, block count and
order. The supplied CRISPR instance has one history, cost 613 before ordering,
and optimized segment cost 653 (19 blocks). The algorithms compare the supplied
histories; they do not infer them or guarantee that the file contains all
optimal InOutParsimony solutions. Multiple-gain histories are rejected until
occurrence expansion is supported.

Optionally provide `--leaf-orders orders.json`, where the file maps each
observed leaf name to its complete order of family names, e.g.
`{"I-C1": ["1", "2", "3\"", "3'", "4", "5", "7", "8"]}`.
Unspecified leaves have no order constraints. These are unsigned orders:
each order and its reversal have the same adjacencies by default. Add
`--respect-leaf-direction` to count an adjacency in the reverse direction as
broken. The option applies to every supplied leaf; it does not impose the
orders as hard constraints or add gene orientations. In particular, unordered
NHX `contents` sets are not interpreted as observed orders.

By default, `--mode pareto` returns one order for every nondominated pair of
weighted segment cost and number of broken leaf adjacencies, across all
supplied histories. This uses exact bounded MaxSAT calls, so it also finds
unsupported Pareto points that a weighted sum may miss. Alternatively,
`--mode weighted --leaf-weight 5` minimizes segment cost plus five per broken
adjacency and returns all tied input histories (one representative order per
history). With no leaf orders both modes select minimum-cost histories.
The number of MaxSAT calls in Pareto mode grows with the number of observed
adjacencies; these calls may be expensive on large instances.

For programmatic use, `synteny_tree.nhx.read_histories` reads the NHX records
and returns their event matrices, which can be passed to `sc1p.solve` or
`scbm.solve`; it is solver-agnostic. `scbm.leaf_orders.solve_weighted` and
`scbm.leaf_orders.pareto_front` optimize column orders with observed leaf
adjacencies, and `scbm.history.compare_histories` compares histories under the
SCBM objective.

## Development

```bash
uv sync --all-extras
uv run pytest
uv run ruff check .
uv run pyright
uv build --all
uvx twine check --strict dist/*
```

## Reproducing the paper

The benchmark results are not stored in the repository. `benchmarks/run.py`
regenerates every matrix from its seed and writes one Parquet directory per
batch, with the matrix, its SHA-256, the per-repeat timings and the solver
statistics. `benchmarks/db.py` loads these directories into DuckDB,
`benchmarks/report.py` computes the statistics and the CSV files, and
`benchmarks/latex.py` draws the figures. See
[`benchmarks/README.md`](benchmarks/README.md) for the exact commands and the
seed used in the paper.

`examples/crispr-class1/` contains the CRISPR-Cas class 1 instance of the
supplementary material: the InOutParsimony history
(`crispr-class1-out-lo20-le10-go1.out.nhx`), its input tree
(`crispr-class1-resolv1.nhx`), the measurements reported in the paper
(`crispr_class1_benchmark.json`), and a script that rebuilds the event matrix
and solves it:

```bash
uv run --all-extras python examples/crispr-class1/run.py
```

It reports the lower bound `17`, the cost `26` of the identity order and the
optimum `19`. Several orders reach this optimum, so the returned order may
differ from the one drawn in the paper.

For weighted costs, observed leaf orders, direction, and Pareto comparisons,
see the [CRISPR example guide](examples/crispr-class1/README.md).

## Citation

See `CITATION.cff` and cite the accompanying paper.

## License

MIT.
