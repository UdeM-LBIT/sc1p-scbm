"""Exact SCBM backends: precedence MaxSAT and brute force."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scbm.exact.brute_force import BruteForceSolver
    from scbm.exact.maxsat import MaxSATSolver

__all__ = [
    "BruteForceSolver",
    "MaxSATSolver",
]

_LAZY = {
    "BruteForceSolver": "scbm.exact.brute_force",
    "MaxSATSolver": "scbm.exact.maxsat",
}


def __getattr__(name: str):
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(module), name)
