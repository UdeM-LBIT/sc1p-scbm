"""SC1P backends: ``sat`` (CaDiCaL through PySAT) and ``brute_force``.

The SAT backend builds the formula :math:`\\Phi(M)` of the paper; brute force
enumerates all ``n!`` orders and serves as the reference implementation.
"""

from __future__ import annotations

from sc1p.registry import SolverRegistry

registry: SolverRegistry = SolverRegistry(
    package="sc1p",
    backend_modules={
        "brute_force": "sc1p.solvers.brute_force",
        "sat": "sc1p.solvers.sat",
    },
    auto_order=("sat", "brute_force"),
    extra_map={"sat": "sat"},
)

register = registry.register
get = registry.get
available = registry.available

__all__ = ["available", "get", "register", "registry"]
