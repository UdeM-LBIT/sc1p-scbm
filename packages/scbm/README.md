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
without it, only the brute-force backend is available.

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

## Command line

```bash
scbm solve '[[1,0,1],[0,1,1],[1,1,0]]' --solver maxsat
scbm analyze '[[1,2,0],[0,1,2]]'
```

## Citation

This package accompanies the paper *Ordering genes to minimize segmental gains
and losses in synteny histories* (Laberge, Delabre, Gascon, El-Mabrouk). See
`CITATION.cff` in the repository and cite the paper.

## License

MIT.
