# sc1p

SAT solver and reference implementation for the **Sandwich Consecutive Ones
Property (SC1P)** of ternary matrices.

A ternary matrix is `M ∈ {0, 1, X}^{m×n}`, stored with `X = 2`. The decision
problem SC1P asks whether some column order `π` makes every row consecutive:
after deleting its `X`-entries, the `1`-entries of the row must be contiguous.
Equivalently, no `0` may lie strictly between the first and last `1` of a row
in the order `π`. For a single-origin synteny tree, SC1P is the decision
problem behind DEMOSH.

## Formulation

For every unordered column pair `1 ≤ a < b ≤ n`, the SAT encoding introduces a
precedence variable `p_{a,b}`, with `p_{b,a} = ¬p_{a,b}`. The formula `Φ(M)`
contains:

- two transitivity clauses per column triple `a < b < c`;
- one anchor agreement `p_{z,a_i} ↔ p_{z,j}` for each row with at least two
  `1`-entries, where `a_i = min J_i^1`, `z ∈ J_i^0`, and
  `j ∈ J_i^1 \ {a_i}`;
- the unit clause `p_{1,2}` when `n ≥ 2`, which keeps one of each reversal pair.

`Φ(M)` is satisfiable iff `M` has SC1P. A model decodes to a witnessing column
order, and `sc1p.verify` checks it in `O(mn)`.

## Install

```bash
# SAT backend, CaDiCaL through PySAT
pip install "sc1p[sat] @ git+https://github.com/UdeM-LBIT/sc1p-scbm#subdirectory=packages/sc1p"
# dependency-free brute-force backend only
pip install "sc1p @ git+https://github.com/UdeM-LBIT/sc1p-scbm#subdirectory=packages/sc1p"
```

## Usage

```python
import sc1p

M = sc1p.sc1p_example()
sat, perm = sc1p.solve(M, solver="sat")
orders = sc1p.solve_all(M)
sc1p.verify(M, perm)
```

`solver="auto"` tries `sat`, then `brute_force`. `sc1p.available()` lists the
loadable backends. A custom backend is a class with `solve` (and optionally
`solve_all`), registered with `sc1p.register("name")`.

## Command line

```bash
sc1p '[[1,2,0],[0,1,2]]'        # {"satisfiable": true, "permutation": [...]}
sc1p '[[1,2,0],[0,1,2]]' --all
```

## Citation

This package accompanies the paper *Ordering genes to minimize segmental gains
and losses in synteny histories* (Laberge, Delabre, Gascon, El-Mabrouk). See
`CITATION.cff` in the repository and cite the paper.

## License

MIT.
