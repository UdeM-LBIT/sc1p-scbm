import json

import pytest

from synteny_tree.leaf_orders import adjacency_rows, index_leaf_orders, read_leaf_orders


def test_read_and_index_leaf_orders(tmp_path):
    path = tmp_path / "orders.json"
    path.write_text(json.dumps({"leaf": ["b", "a"]}))

    orders = read_leaf_orders(path)

    assert orders == {"leaf": ("b", "a")}
    assert index_leaf_orders(orders, {"leaf": {"a", "b"}}, ["a", "b", "c"]) == [[1, 0]]


@pytest.mark.parametrize(
    ("orders", "contents", "families"),
    [
        ({"missing": ["a"]}, {"leaf": {"a"}}, ["a"]),
        ({"leaf": ["a"]}, {"leaf": {"a", "b"}}, ["a", "b"]),
        ({"leaf": ["z"]}, {"leaf": {"z"}}, ["a"]),
    ],
)
def test_index_leaf_orders_rejects_invalid_orders(orders, contents, families):
    with pytest.raises(ValueError):
        index_leaf_orders(orders, contents, families)


def test_adjacency_rows_are_ternary_and_allow_reversal():
    assert adjacency_rows(4, [[0, 1, 2]]) == [[1, 1, 0, 2], [0, 1, 1, 2]]
    assert adjacency_rows(4, [[0, 1, 2]])[::-1] == adjacency_rows(4, [[2, 1, 0]])
