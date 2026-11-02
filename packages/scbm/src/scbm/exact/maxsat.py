"""The weighted partial MaxSAT instance ``Ψ(M) = (H, S)`` of SCBM, solved with RC2.

The hard clauses ``H`` reuse the precedence variables ``p_{a,b}`` of the SC1P
encoding: one variable per unordered pair, the transitivity clauses of
:mod:`sc1p.encoding.sat`, and the unit clause ``p_{1,2}`` for reversal
symmetry. Rows are split into ``R_0`` (no ``1``), ``R_1`` (one ``1`` or no
``0``, hence one block in every order) and the active rows ``A``. A variable
``f`` with the hard clause ``(f)`` and the soft clause ``(¬f)`` of weight
``|R_1|`` counts the rows of ``R_1``. In an active row ``i``, for distinct
``1``-columns ``ℓ`` (left) and ``r`` (right) and another ``1``- or
``0``-column ``c`` (center)::

    bet_{i,ℓ,c,r} ↔ p_{ℓ,c} ∧ p_{c,r}
    succ_{i,ℓ,r}  ↔ p_{ℓ,r} ∧ ⋀_c ¬bet_{i,ℓ,c,r}
    head_{i,r}    ↔ ¬⋁_ℓ succ_{i,ℓ,r}

and each ``head_{i,r}``, true when ``r`` is the first ``1`` of a block, falsifies
a soft clause ``(¬head_{i,r})`` of weight one. The clauses are those of
Algorithm S2 of the supplementary material, and the RC2 optimum is ``b(M^π)``.

Requires ``pip install 'scbm[sat]'``.
"""

from __future__ import annotations

from pysat.examples.rc2 import RC2
from pysat.formula import WCNF

from sc1p import validate_ternary
from sc1p.encoding.sat import extract_perm, num_pairs, pair_index, transitivity_triples
from scbm import register
from scbm.score import block_cost
from scbm.types import Matrix, OptimizeResult, Permutation


class _Builder:
    """WCNF builder whose fresh variables start above the precedence block."""

    def __init__(self, top: int) -> None:
        self.wcnf = WCNF()
        self.top = top

    def var(self) -> int:
        self.top += 1
        return self.top

    def hard(self, clause: list[int]) -> None:
        self.wcnf.append(list(clause))

    def soft(self, clause: list[int], weight: int = 1) -> None:
        self.wcnf.append(list(clause), weight=weight)


def _before(x: int, y: int, n: int) -> int:
    """PySAT literal of "column x precedes column y"."""
    if x < y:
        return pair_index(x, y, n) + 1
    return -(pair_index(y, x, n) + 1)


def _add_row(builder: _Builder, n: int, ones: list[int], zeros: list[int]) -> None:
    """Add the ``bet``, ``succ`` and ``head`` variables of one active row."""
    succ: dict[tuple[int, int], int] = {}
    for left in ones:
        for right in ones:
            if left != right:
                succ[(left, right)] = builder.var()

    for (left, right), q in succ.items():
        centers = [c for c in ones + zeros if c != left and c != right]
        bet: dict[int, int] = {}
        for c in centers:
            bet[c] = builder.var()
            # bet_{i,ℓ,c,r} ↔ p_{ℓ,c} ∧ p_{c,r}
            builder.hard([-bet[c], _before(left, c, n)])
            builder.hard([-bet[c], _before(c, right, n)])
            builder.hard([bet[c], -_before(left, c, n), -_before(c, right, n)])
        # succ_{i,ℓ,r} ↔ p_{ℓ,r} ∧ ⋀_c ¬bet_{i,ℓ,c,r}
        builder.hard([-q, _before(left, right, n)])
        for c in centers:
            builder.hard([-q, -bet[c]])
        builder.hard([q, -_before(left, right, n)] + [bet[c] for c in centers])

    for right in ones:
        head = builder.var()
        lefts = [left for left in ones if left != right]
        # head_{i,r} ↔ ¬⋁_ℓ succ_{i,ℓ,r}
        for left in lefts:
            builder.hard([-head, -succ[(left, right)]])
        builder.hard([head] + [succ[(left, right)] for left in lefts])
        builder.soft([-head], weight=1)


def build_psi(matrix: Matrix, n: int) -> tuple[WCNF | None, int]:
    """Return ``(Ψ(M), |R_1|)``, or ``(None, |R_1|)`` when ``A`` is empty.

    The unit clause ``p_{1,2}`` keeps one order from each reversal pair; the
    caller restores the missing reversals when enumerating all optima.
    """
    active: list[tuple[list[int], list[int]]] = []
    r1 = 0
    for row in matrix:
        ones = [j for j in range(n) if row[j] == 1]
        if not ones:
            continue
        zeros = [j for j in range(n) if row[j] == 0]
        if len(ones) == 1 or not zeros:
            r1 += 1
        else:
            active.append((ones, zeros))

    if not active:
        return None, r1

    builder = _Builder(top=num_pairs(n))
    for ab, bc, ac in transitivity_triples(n):
        builder.hard([-(ab + 1), -(bc + 1), ac + 1])
        builder.hard([ab + 1, bc + 1, -(ac + 1)])
    if n >= 2:
        builder.hard([_before(0, 1, n)])

    if r1:
        f = builder.var()
        builder.hard([f])
        builder.soft([-f], weight=r1)

    for ones, zeros in active:
        _add_row(builder, n, ones, zeros)
    return builder.wcnf, r1


@register("maxsat")
class MaxSATSolver:
    def solve(self, matrix: Matrix) -> OptimizeResult:
        m, n = validate_ternary(matrix)
        identity = list(range(n))
        if n <= 1 or m == 0:
            return OptimizeResult(identity, block_cost(matrix, identity))

        wcnf, _ = build_psi(matrix, n)
        if wcnf is None:
            return OptimizeResult(identity, block_cost(matrix, identity))

        with RC2(wcnf) as rc2:
            model = rc2.compute()
            cost = rc2.cost
        if model is None:
            return OptimizeResult(identity, block_cost(matrix, identity))
        truth = {abs(value): value > 0 for value in model}
        permutation = extract_perm(truth, n, one_indexed=True)
        return OptimizeResult(permutation, cost)

    def solve_all(self, matrix: Matrix) -> list[Permutation]:
        """Every optimal column order, enumerated by RC2.

        The encoding keeps one order from each reversal pair. RC2 blocks each
        optimal representative in turn, and both the representative and its
        reverse are returned. The enumeration stops as soon as the next MaxSAT
        model costs more, so no ``n!`` enumeration is performed.
        When no row is active, every order is optimal and this method returns
        all ``n!`` permutations, which is inherent to the output size.
        """
        from itertools import permutations

        m, n = validate_ternary(matrix)
        identity = list(range(n))
        if n <= 1 or m == 0:
            return [identity]

        wcnf, _ = build_psi(matrix, n)
        if wcnf is None:
            return [list(perm) for perm in permutations(range(n))]

        orders: list[Permutation] = []
        seen: set[tuple[int, ...]] = set()

        def add(permutation: Permutation) -> None:
            for candidate in (permutation, permutation[::-1]):
                key = tuple(candidate)
                if key not in seen:
                    seen.add(key)
                    orders.append(candidate)

        optimum: int | None = None
        with RC2(wcnf) as rc2:
            for model in rc2.enumerate():
                if optimum is None:
                    optimum = rc2.cost
                elif rc2.cost > optimum:
                    break
                truth = {abs(value): value > 0 for value in model}
                add(extract_perm(truth, n, one_indexed=True))
        return orders
