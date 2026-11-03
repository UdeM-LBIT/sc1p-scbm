# synteny-tree

Event matrices of synteny trees, for the [`sc1p`](../sc1p) and
[`scbm`](../scbm) solvers.

A synteny tree `⟨T, x⟩` is a rooted tree `T` together with the synteny (set of
gene families) `x(v)` of **every** node, root and internal nodes included;
contents are never inferred from the leaves. As in the paper, the planted tree
adds a root of empty content above `T`, so the planted edge gains the content
of the root. With the edges of the planted tree:

- the **loss matrix** `M⁻` has one row per edge `(u, v)` losing families:
  `1` for a family of `x(u) - x(v)`, `0` for a family of `x(u) ∩ x(v)`, and
  `X` for a family absent from `x(u)`;
- the **gain matrix** `M⁺` has one row per edge gaining families: `1` for a
  family of `x(v) - x(u)`, `0` for a family of `x(u) ∩ x(v)`, and `X` for a
  family absent from `x(v)`;
- the **event matrix** `M` is `M⁻` stacked on `M⁺`.

Matrices store `X` as `2`. For a single-origin synteny tree, in which every
family is gained on exactly one edge, `M` can be passed directly to
`scbm.solve` (MOSH) or `sc1p.solve` (DEMOSH). `event_matrix` raises
`NotSingleOriginError` on other trees; `occurrence_expansion` then builds the
occurrence-expanded tree of the paper, which is single-origin, with one column
per occurrence `(family, i)`, where `e_i` is the edge gaining it.

## Install

```bash
pip install "synteny-tree @ git+https://github.com/UdeM-LBIT/sc1p-scbm#subdirectory=packages/synteny-tree"
```

The only dependency is the [sowing](https://github.com/UdeM-LBIT/sowing) tree
library.

## Usage

```python
from sowing import Node
from synteny_tree import event_matrix, gain_matrix, loss_matrix
from synteny_tree.leaf_orders import adjacency_rows, index_leaf_orders, read_leaf_orders

tree = Node("ρ").add(Node("u").add(Node("v")).add(Node("w")))
x = {
    "ρ": frozenset({0, 1, 2}),
    "u": frozenset({0, 1}),
    "v": frozenset({0}),
    "w": frozenset({0, 1}),
}
M = event_matrix(tree, x, families=(0, 1, 2))  # [[0, 0, 1], [0, 1, 2], [1, 1, 1]]
M_loss = loss_matrix(tree, x, families=(0, 1, 2))  # M⁻
M_gain = gain_matrix(tree, x, families=(0, 1, 2))  # M⁺, the planted edge
```

The tree may also be a Newick string whose labels, internal nodes included,
are the keys of `x` (`event_matrix("((v,w)u)ρ;", x)`), or a `sowing.Node`
whose `node.data` already holds the content (`event_matrix(tree)`). The
contents may also be given by a function `Node -> set of families`. A node
without content raises `IncompleteSyntenyTreeError`. `families` sets the
column order; by default, families are numbered in order of first appearance
in a depth-first walk.

For a tree in which some family is gained several times:

```python
from synteny_tree import event_matrix, is_single_origin, occurrence_expansion

if not is_single_origin(tree, x):
    M = event_matrix(occurrence_expansion(tree, x))
```

Observed orders at leaves are represented as a mapping from leaf names to
ordered family labels. `read_leaf_orders` reads this mapping from JSON,
`index_leaf_orders` validates each order against its leaf content and converts
families to matrix columns, and `adjacency_rows` encodes consecutive pairs as
ternary constraints. These helpers are independent of the SC1P and SCBM
optimization objectives.

## InOutParsimony histories

`read_histories` reads the `solutions show` NHX output of InOutParsimony: one
record per solution, with the content of every node in a `contents`
annotation. Each history exposes its tree, contents, families and event matrix,
so the matrix can be passed to `sc1p.solve` or `scbm.solve`. The reported
InOutParsimony cost is kept for comparison.

```python
from synteny_tree.nhx import EventCosts, read_histories

(history,) = read_histories("solutions.nhx")
history.matrix  # event matrix M
history.inout_cost(EventCosts(loss_open=20, loss_ext=10, gain_open=1))
```

A history that gains a family on several edges is rejected; apply
`occurrence_expansion` before building its matrix. The reader needs only
`sowing`.

## Citation

This package accompanies the paper *Ordering genes to minimize segmental gains
and losses in synteny histories* (Laberge, Delabre, Gascon, El-Mabrouk). See
`CITATION.cff` in the repository and cite the paper.

## License

MIT.
