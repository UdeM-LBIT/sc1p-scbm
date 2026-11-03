# CRISPR-Cas class 1: reproducing the examples

Run these commands from the repository root after `uv sync --all-extras`. They
use the supplied **single** InOutParsimony solution; they do not enumerate or
infer other histories.

## Input files

- `crispr-class1-resolv1.nhx`: original tree; leaf contents are unordered sets.
- `crispr-class1-out-lo20-le10-go1.out.nhx`: inferred tree with the content of
  every node; its header reports InOutParsimony cost 613.
- `leaf-orders-two.json`: orders for just two leaves, III-F and IV-B, read from
  Extended Data Figure 2 of [Makarova et al. (2025)](https://doi.org/10.1038/s41564-025-02180-8).
  These are a **partial illustration**, not orders for the other 13 leaves.
- `run.py` and `crispr_class1_benchmark.json`: the original unweighted
  benchmark and its recorded measurements.

The JSON maps a leaf name to its family labels in order. Each listed leaf must
contain exactly the same families as its NHX content. Leaves omitted from the
file have no observed-order criterion. The labels `3"` and `3'` are distinct;
in JSON, `3"` is written as `"3\""`. The NHX `contents` values are sets and
must not be treated as observed gene orders.

## 1. Original unweighted SCBM benchmark

```bash
uv run --all-extras python examples/crispr-class1/run.py
```

The matrix has 17 event rows and 11 families; the lower bound is 17, the
identity order costs 26 blocks, and the minimum is **19 blocks**. Running times
are machine-dependent; the returned optimal order need not be unique.

## 2. Variable gain and loss costs, without leaf orders

```bash
uv run --all-extras scbm history \
  examples/crispr-class1/crispr-class1-out-lo20-le10-go1.out.nhx \
  --loss-open 20 --loss-ext 10 --gain-open 1 --gain-ext 0
```

For an event of size `k`, the cost is `open + extension * k`. The JSON reports
an InOutParsimony cost of **613** and an optimal segmental cost of **653**,
with 19 blocks. These are different objectives: the ordered history splits
some original loss events into multiple segments.

## 3. Pareto front with two observed leaf orders

```bash
uv run --all-extras scbm history \
  examples/crispr-class1/crispr-class1-out-lo20-le10-go1.out.nhx \
  --leaf-orders examples/crispr-class1/leaf-orders-two.json \
  --loss-open 20 --loss-ext 10 --gain-open 1 --gain-ext 0 \
  --mode pareto
```

With reversal allowed, the nondominated pairs `(history_cost,
broken_adjacencies)` are **(673, 1)** and **(653, 2)**. The pairs correspond
to 20 and 19 blocks respectively. The returned orders are representatives;
other orders can attain the same pair. The first pair is the lexicographic
choice used in figure S5 of the supplement: minimize broken adjacencies, then
history cost. The unobserved leaves are not scored.

For other candidate histories, pass an InOutParsimony NHX output containing
multiple `# solution no. ..., cost=...` records. The Pareto front is computed
across all supplied histories, with one order per nondominated pair per
history. The program does not assume that these histories have equal
InOutParsimony costs: use optimal histories if the goal is to break ties among
InOutParsimony optima. A single-origin history is required.

## 4. Weighted compromise and direction

```bash
uv run --all-extras scbm history \
  examples/crispr-class1/crispr-class1-out-lo20-le10-go1.out.nhx \
  --leaf-orders examples/crispr-class1/leaf-orders-two.json \
  --loss-open 20 --loss-ext 10 --gain-open 1 --gain-ext 0 \
  --mode weighted --leaf-weight 25
```

This minimizes `history_cost + 25 * broken_adjacencies`; the chosen pair is
`(673, 1)`. Set `--leaf-weight 0` to ignore the leaf orders, or choose another
non-negative integer. Per-event costs and the adjacency weight are currently
non-negative integers.

By default, a leaf order and its reverse are equivalent. To count directed
adjacencies instead, add `--respect-leaf-direction` to either the `pareto` or
`weighted` command. This keeps gene labels unsigned and makes the direction
of each adjacent pair matter; the leaf order is still a soft criterion, not a
hard constraint. With direction respected, the example Pareto pairs remain
`(673, 1)` and `(653, 2)`, although the representative orders differ.

## Preparing additional input

`scbm history` expects the NHX solution format illustrated by the supplied
`*.out.nhx`, including the `contents` annotation of every internal and leaf
node. Versions of InOutParsimony that print a human-readable event tree instead
of NHX need a separate export/conversion step; the CLI does not parse that
format. To compare several solutions, export them as multiple NHX records in
one file. Then replace the NHX path in the commands above and provide any
available leaf orders as JSON.
