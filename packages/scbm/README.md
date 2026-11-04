# scbm

Exact MaxSAT solver for the **Sandwich Consecutive-Block Minimization (SCBM)**
problem on ternary matrices.

A ternary matrix is `M ∈ {0, 1, X}^{m×n}`, stored with `X = 2`. Given a column
order `π`, a *block* of a row of `M^π` is a substring without `0` that starts
and ends with a `1`, and a *maximal block* is a block not included in a larger
one. Write `b(M^π)` for the number of maximal blocks of `M^π`; SCBM asks for a
column order minimizing it:

```
SCBM(M) = min_{π ∈ Order([n])} b(M^π).
```

Rows without a `1` contribute zero. On an event matrix, every row contains a
`1` and contributes at least one block, so `b(M^π) ≥ λ + γ`, and equality holds
exactly when the matrix has SC1P. For a single-origin synteny tree, MOSH
reduces to SCBM on its event matrix.

## Formulation

The package implements the weighted partial MaxSAT encoding `Ψ(M) = (H, S)` of
the paper's supplementary material (Algorithm S2). It reuses the precedence
variables `p_{a,b}` and transitivity clauses of the SC1P encoding. For each
active row `i ∈ A` and each ordered pair of `1`-columns `(ℓ, r)`, auxiliary
variables `bet_{i,ℓ,c,r}` and `succ_{i,ℓ,r}` identify adjacent `1`-columns
after deleting `X`; `head_{i,r}` marks the first `1` of a block. Each
`head_{i,r}` falsifies a unit soft clause of weight one. The rows of `R_1`,
which have one block in every order, are counted by a variable `f` with a soft
clause of weight `|R_1|`.

The raw RC2 optimum is `b(M^π)`; no lower-bound offset is added.

## Install

```bash
pip install \
  "sc1p @ git+https://github.com/UdeM-LBIT/sc1p-scbm#subdirectory=packages/sc1p" \
  "scbm[sat] @ git+https://github.com/UdeM-LBIT/sc1p-scbm#subdirectory=packages/scbm"
```

`scbm` depends on `sc1p`, which is not on PyPI, so both are installed from
the repository. The `sat` extra pulls in the MaxSAT backend (PySAT/RC2);
without it, only the brute-force backend is available. The `history` extra
pulls in `synteny-tree` for the `scbm history` command.

## Usage

```python
import scbm

M = [[1, 0, 1], [0, 1, 1], [1, 1, 0]]
perm, cost = scbm.solve(M, solver="maxsat")
scbm.score.block_cost(M, perm)       # b(M^π)
scbm.score.block_lower_bound(M)      # rows containing a 1; λ+γ on an event matrix
report = scbm.analyze(M)             # has_sc1p iff cost == lower bound
solutions = scbm.solve_all(M)        # every optimal order; backend enumeration
```

`solver="auto"` tries `maxsat`, then `brute_force`. A custom backend is a class
with `solve`, registered with `scbm.register("name")`.

## Event matrices

To build the event matrix of a synteny tree (a tree with the synteny of every
node), use the [`synteny-tree`](../synteny-tree) package of the same
repository; its output can be passed directly to `scbm.solve`.

`scbm history` compares one or more single-origin histories read from an
InOutParsimony NHX output, using `synteny_tree.nhx.read_histories`. It reports
the InOutParsimony cost and the optimized segment cost of each candidate, and
optionally trades cost against observed leaf adjacencies. See the repository
README and [`examples/crispr-class1`](../../examples/crispr-class1).

## Command line

```bash
scbm solve '[[1,0,1],[0,1,1],[1,1,0]]' --solver maxsat
scbm analyze '[[1,2,0],[0,1,2]]'
scbm history solutions.nhx --leaf-orders orders.json --mode pareto
scbm history solutions.nhx --leaf-orders orders.json --mode pareto --leaf-criterion extension
scbm history resolution1.nhx resolution2.nhx --leaf-orders orders.json --mode pareto
```

The default Pareto leaf criterion is the number of broken observed adjacencies.
With `--leaf-criterion extension`, the second objective is the raw cost of
added pair-loss events. For each observed order `(a, b, c, d)`, the added
losses are `{a,b}`, `{b,c}`, and `{c,d}`, each in the context of that leaf's
families. As in the supplementary paper's leaf-order augmentation, internal
nodes retain the full leaf content; each pair is lost on an edge to a new leaf,
and an additional leaf retains the full content. The implementation scores the
resulting loss rows without constructing the augmented tree. Each loss costs
`loss_open * blocks + loss_ext * 2`. Thus, for `m`
observed pairs and `d` broken adjacencies, the extension cost is
`loss_open * (m + d) + 2 * loss_ext * m`. JSON results include `history_cost`,
`extension_cost`, and their sum `total_cost`.

For a positive loss opening cost, this criterion gives the same Pareto front as
broken adjacencies, expressed in cost units. It is a soft criterion, not a
constraint requiring all observed adjacencies to be preserved. This mode
accepts unsigned orders up to reversal and cannot be combined with
`--respect-leaf-direction` or `--mode weighted`.

Each NHX file gets its own Pareto front (or weighted optimum), comparing any
histories within that file. The report identifies each history by its file and
solution; each supplied leaf order must match every history. Files are
processed sequentially.
Add `--global-front` to compare histories from all input files together
instead, retaining a single nondominated front (or global weighted optimum).

On a terminal, `scbm history` prints a Rich report (cost model, history
summary, solutions table, family orders grouped by result, tree);
when the output is redirected it prints JSON.
`--format json` or `--format rich` forces either, independently of the terminal,
`--tree` appends the input history tree before ordering, with each node's
contents and the families lost or gained on its incoming branch,
and `--all` returns optimal orders instead of one representative per Pareto
pair. When reversal is equivalent, orders and counts include one representative
per reversal pair; with directed leaf adjacencies, both directions are retained.
The JSON field `orders_up_to_reversal` indicates which rule applies. The solutions
table shows each `(cost, broken)` pair once, with the number of orders attaining
it; `--all` lists the orders in the family-order section. Pareto mode enumerates optimal orders
to count them even without `--all`, which may take time. In weighted mode, the
count is omitted unless `--all` is used. On a terminal, progress is reported to
standard error as each history is solved; redirected JSON remains unchanged.

## Citation

This package accompanies the paper *Ordering genes to minimize segmental gains
and losses in synteny histories* (Laberge, Delabre, Gascon, El-Mabrouk). See
`CITATION.cff` in the repository and cite the paper.

## License

MIT.
