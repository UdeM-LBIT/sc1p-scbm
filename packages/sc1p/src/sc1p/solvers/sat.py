"""The SAT formula ``Φ(M)`` of SC1P, solved with CaDiCaL through PySAT.

For every column pair ``1 ≤ a < b ≤ n``, the precedence variable ``p_{a,b}``
means that column ``a`` precedes column ``b``, and ``p_{b,a} = ¬p_{a,b}``.
Transitivity clauses make ``<_{α}`` a strict total order. For each row with at
least two ``1``s and one ``0``, the first ``1``-column ``a_i`` is the anchor, and
every ``0``-column ``z`` and other ``1``-column ``j`` get
``p_{z,a_i} ↔ p_{z,j}``: ``z`` is on the same side of every ``1``. The unit
clause ``p_{1,2}`` keeps one order from each reversal pair. The clauses are
those of Algorithm S1 of the supplementary material; an equivalence required
by several rows is added once.

Requires ``pip install 'sc1p[sat]'``.
"""

from __future__ import annotations

from pysat.formula import CNF
from pysat.solvers import Solver

from sc1p.encoding.sat import extract_perm, num_pairs, pair_index, transitivity_triples
from sc1p.solvers import register
from sc1p.ternary import validate_ternary
from sc1p.types import Matrix, Permutation, SolveResult
from sc1p.verify import verify


def _before(x: int, y: int, n: int) -> int:
    """PySAT literal of "column x precedes column y"."""
    if x < y:
        return pair_index(x, y, n) + 1
    return -(pair_index(y, x, n) + 1)


def build_phi(matrix: Matrix, n: int, *, symmetry_break: bool) -> CNF:
    """Phi(M). *symmetry_break* adds one unit clause that keeps one of each
    order/reversal pair; satisfiability is unchanged but the model set halves.
    """
    cnf = CNF()
    for ab, bc, ac in transitivity_triples(n):
        cnf.append([-(ab + 1), -(bc + 1), ac + 1])
        cnf.append([ab + 1, bc + 1, -(ac + 1)])

    if symmetry_break and n >= 2:
        cnf.append([_before(0, 1, n)])

    emitted: set[tuple[int, int, int]] = set()
    for row in matrix:
        ones = [j for j in range(n) if row[j] == 1]
        zeros = [j for j in range(n) if row[j] == 0]
        if len(ones) < 2:
            continue
        anchor = ones[0]
        for z in zeros:
            z_anchor = _before(z, anchor, n)
            for j in ones[1:]:
                if (z, anchor, j) in emitted:
                    continue
                emitted.add((z, anchor, j))
                z_j = _before(z, j, n)
                cnf.append([-z_anchor, z_j])
                cnf.append([z_anchor, -z_j])
    return cnf


def _truth(solver: Solver) -> dict[int, bool]:
    model = solver.get_model()
    assert model is not None
    return {abs(v): v > 0 for v in model}


@register("sat")
class SATSolver:
    def __init__(self, solver_name: str = "cadical153"):
        self.solver_name = solver_name

    def solve(self, matrix: Matrix) -> SolveResult:
        _, n = validate_ternary(matrix)
        if n <= 1:
            return SolveResult(True, list(range(n)))
        with Solver(
            name=self.solver_name,
            bootstrap_with=build_phi(matrix, n, symmetry_break=True),
        ) as solver:
            if not solver.solve():
                return SolveResult(False, None)
            perm = extract_perm(_truth(solver), n, one_indexed=True)
        assert verify(matrix, perm)
        return SolveResult(True, perm)

    def solve_all(self, matrix: Matrix) -> list[Permutation]:
        """Every SC1P order, by adding one blocking clause per model found."""
        _, n = validate_ternary(matrix)
        if n <= 1:
            return [list(range(n))]
        solutions: list[Permutation] = []
        with Solver(
            name=self.solver_name,
            bootstrap_with=build_phi(matrix, n, symmetry_break=False),
        ) as solver:
            while solver.solve():
                truth = _truth(solver)
                perm = extract_perm(truth, n, one_indexed=True)
                assert verify(matrix, perm)
                solutions.append(perm)
                solver.add_clause(
                    [-(i + 1) if truth.get(i + 1, False) else i + 1 for i in range(num_pairs(n))]
                )
        return solutions
