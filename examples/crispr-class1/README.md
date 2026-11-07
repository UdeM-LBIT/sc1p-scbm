# CRISPR-Cas class 1: reproducing the examples

Run these commands from the repository root after `uv sync --all-extras`. They
use supplied InOutParsimony solutions; they do not infer other histories.

## Input files

- `crispr-class1-resolv1.nhx`: original tree; leaf contents are unordered sets.
- `crispr-class1-out-lo20-le10-go1.out.nhx`: inferred tree with the content of
  every node; its header reports InOutParsimony cost 574.
- `../../results/pareto-24/`: the 24 inferred histories and orders for all 15
  leaves supplied in `emeric(deux).zip`, including
  `crispr-class1-resolvI-III-out-lo1-le1-go1.nhx` and `crispr-class1-order.json`.
  The orders were read from Extended Data Figure 2 of
  [Makarova et al. (2025)](https://doi.org/10.1038/s41564-025-02180-8).
  The historical 574-cost NHX is not compatible with these orders: its IV-A1
  leaf additionally contains families `1` and `2`.
- `../../results/pareto-24-gain-ext1/pareto-global-24.{json,txt}`: the Pareto
  front of the paper's Table 1 and Table H.1, under unit costs.

The JSON maps a leaf name to its family labels in order. Each listed leaf must
contain exactly the same families as its NHX content. Leaves omitted from the
file have no observed-order criterion. The labels `3"` and `3'` are distinct;
in JSON, `3"` is written as `"3\""`. The NHX `contents` values are sets and
must not be treated as observed gene orders.

## 1. A single history, without leaf orders

```bash
uv run --all-extras scbm history \
  examples/crispr-class1/crispr-class1-out-lo20-le10-go1.out.nhx \
  --loss-open 20 --loss-ext 10 --gain-open 1 --gain-ext 0
```

For an event of size `k`, the cost is `open + extension * k`. The JSON reports
an InOutParsimony cost of **574** and an optimal segmental cost of **574**,
with 18 blocks. These are different objectives: the ordered history splits
some original loss events into multiple segments.

## 2. Pareto front with the observed leaf orders

```bash
uv run --all-extras scbm history \
  results/pareto-24/crispr-class1-resolvI-III-out-lo1-le1-go1.nhx \
  --leaf-orders results/pareto-24/crispr-class1-order.json \
  --loss-open 1 --loss-ext 1 --gain-open 1 --gain-ext 0 \
  --mode pareto
```

The file contains eight inferred histories. With reversal allowed, their
combined nondominated pairs `(history_cost, broken_adjacencies)` are
**(46, 22)**, **(44, 23)** and **(43, 26)**. The first two occur in histories
3 and 4; the last occurs in history 4. The returned orders are representatives;
the `solutions` field gives the number of orders attaining each pair for each
history, up to reversal.

For other candidate histories, pass an InOutParsimony NHX output containing
multiple `# solution no. ..., cost=...` records. The Pareto front is computed
across all supplied histories, with one order per nondominated pair per
history. The program does not assume that these histories have equal
InOutParsimony costs: use optimal histories if the goal is to break ties among
InOutParsimony optima. A single-origin history is required.

## 3. The paper's Table 1: all 24 histories, unit costs

Section 9 of the paper sets loss opening, loss extension, gain opening and
gain extension to 1, so an event of `k` families costs `1 + k`; it then
extends each leaf with the adjacencies of its observed order (the caterpillar
of Section 6.2) and keeps the Pareto front over `(cost_T, cost_T')`.
`--leaf-criterion extension` adds one loss row per leaf adjacency and reports
the cost of those rows alone as the second objective.
Comparing all three root resolutions in one run (about two minutes):

```bash
uv run --all-extras scbm history \
  results/pareto-24/crispr-class1-resolvI-III-out-lo1-le1-go1.nhx \
  results/pareto-24/crispr-class1-resolvI-IV-out-lo1-le1-go1.nhx \
  results/pareto-24/crispr-class1-resolvIII-IV-out-lo1-le1-go1.nhx \
  --leaf-orders results/pareto-24/crispr-class1-order.json \
  --loss-open 1 --loss-ext 1 --gain-open 1 --gain-ext 1 \
  --mode pareto --leaf-criterion extension --global-front --all --format json
```

The result is checked in as
`results/pareto-24-gain-ext1/pareto-global-24.{json,txt}`. The global front has
eleven orders but only three distinct `(cost_T, broken_adjacencies)` pairs —
`(57, 22)`, `(55, 23)` and `(54, 26)`, all from the I--III resolution — and the
report gives `extension_cost` and `total_cost` for each of them:
**(57, 316)**, **(55, 315)** and **(54, 317)**.

`extension_cost` is `3 * 79 + d`, where 79 is the total number of leaf
adjacencies (one per consecutive pair of every leaf order) and `d` the number
of broken ones: an intact adjacency costs one loss of two families, a broken
one two such losses. `total_cost` is `cost_T + extension_cost`.

`(57, 316)` is nondominated in `(cost_T, d)`, the front listed in Table H.1 of
the supplementary material, but it is dominated by `(55, 315)` once the
objectives are `(cost_T, cost_T')`. Table 1 of the paper reports that
projection, hence **two** rows.

## 4. Weighted compromise and direction

```bash
uv run --all-extras scbm history \
  results/pareto-24/crispr-class1-resolvI-III-out-lo1-le1-go1.nhx \
  --leaf-orders results/pareto-24/crispr-class1-order.json \
  --loss-open 1 --loss-ext 1 --gain-open 1 --gain-ext 0 \
  --mode weighted --leaf-weight 25
```

This minimizes `history_cost + 25 * broken_adjacencies`; the chosen pair is
`(46, 22)` for histories 3 and 4. Set `--leaf-weight 0` to ignore the leaf orders, or choose another
non-negative integer. Per-event costs and the adjacency weight are currently
non-negative integers.

By default, a leaf order and its reverse are equivalent. To count directed
adjacencies instead, add `--respect-leaf-direction` to either the `pareto` or
`weighted` command. This keeps gene labels unsigned and makes the direction
of each adjacent pair matter; the leaf order is still a soft criterion, not a
hard constraint. With direction respected, the example Pareto pairs become
`(46, 27)`, `(44, 28)` and `(43, 37)`.

## Preparing additional input

`scbm history` expects the NHX solution format illustrated by the supplied
`*.out.nhx`, including the `contents` annotation of every internal and leaf
node. Versions of InOutParsimony that print a human-readable event tree instead
of NHX need a separate export/conversion step; the CLI does not parse that
format. To compare several solutions, export them as multiple NHX records in
one file. Then replace the NHX path in the commands above and provide any
available leaf orders as JSON.
