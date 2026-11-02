from __future__ import annotations

import random

import sc1p

CROSS_CHECK_MATRICES = [
    [[1, 0, 1], [0, 1, 1], [1, 1, 0]],
    [[1, 0, 0, 1]],
    [[1, 0, 1, 0, 1]],
    [[1, 1, 0, 0], [0, 0, 1, 1], [1, 0, 0, 1]],
    sc1p.sc1p_example(),
]


def random_matrices(n_each: int = 6) -> list[sc1p.Matrix]:
    rng = random.Random(7)
    return [
        sc1p.random_matrix(m, n, p1=0.3, p0=0.5, rng=rng)
        for m in range(2, 7)
        for n in range(m, 7)
        for _ in range(n_each)
    ]
