from __future__ import annotations

import pytest

import sc1p
import scbm


@pytest.fixture
def paper_matrix() -> sc1p.Matrix:
    return sc1p.sc1p_example()


@pytest.fixture
def satisfiable_matrix() -> sc1p.Matrix:
    return [
        [1, 1, 0],
        [0, 1, 1],
    ]


@pytest.fixture
def unsatisfiable_matrix() -> sc1p.Matrix:
    """Every pair of columns must be adjacent, which three columns cannot satisfy."""
    return [
        [1, 0, 1],
        [0, 1, 1],
        [1, 1, 0],
    ]


@pytest.fixture(params=["brute_force", "sat"])
def sc1p_solver(request) -> str:
    if request.param not in sc1p.available():
        pytest.skip(f"SC1P backend {request.param!r} is not installed")
    return request.param


@pytest.fixture(params=["brute_force", "maxsat"])
def scbm_solver(request) -> str:
    if request.param not in scbm.available():
        pytest.skip(f"SCBM backend {request.param!r} is not installed")
    return request.param
