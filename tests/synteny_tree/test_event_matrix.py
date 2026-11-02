"""Loss, gain and event matrices of a synteny tree, as defined in the paper."""

from __future__ import annotations

import pytest
from sowing import Node

import sc1p
import scbm
from scbm.score import block_cost, block_lower_bound
from synteny_tree import (
    IncompleteSyntenyTreeError,
    NotSingleOriginError,
    X,
    event_matrix,
    gain_matrix,
    is_single_origin,
    loss_matrix,
    occurrence_expansion,
)

# Root ρ — internal u — leaves v, w. Families a,b,c = 0,1,2.
# x(ρ)={a,b,c}, x(u)={a,b}, x(v)={a}, x(w)={a,b}.
_CONTENTS = {
    "ρ": frozenset({0, 1, 2}),
    "u": frozenset({0, 1}),
    "v": frozenset({0}),
    "w": frozenset({0, 1}),
}


def _id_tree() -> Node:
    return Node("ρ").add(Node("u").add(Node("v")).add(Node("w")))


def _figure_1() -> tuple[Node, dict[int, frozenset[str]]]:
    """Synteny tree of Figure 1 of the paper; node ids are the edge numbers
    of their parent edge, with the root reached by the planted edge 1."""
    tree = (
        Node(1)
        .add(Node(2).add(Node(4).add(Node(6)).add(Node(7))).add(Node(5)))
        .add(Node(3).add(Node(8)).add(Node(9)))
    )
    x = {
        1: "bcd",
        2: "abcdef",
        3: "bcdhi",
        4: "afg",
        5: "abcdef",
        6: "afg",
        7: "g",
        8: "bdh",
        9: "cdi",
    }
    return tree, {node: frozenset(content) for node, content in x.items()}


def test_loss_matrix_rows():
    # Root {a,b,c}; left loses c; right loses b. Families a,b,c = 0,1,2.
    a, b, c = 0, 1, 2
    tree = Node(frozenset({a, b, c})).add(Node(frozenset({a, b}))).add(Node(frozenset({a, c})))
    M = loss_matrix(tree, families=(a, b, c))
    assert M == [
        [0, 0, 1],  # lose c, keep a,b
        [0, 1, 0],  # lose b, keep a,c
    ]
    gains = gain_matrix(tree, families=(a, b, c))
    assert gains == [[1, 1, 1]]  # planted edge: gain of the root content
    assert event_matrix(tree, families=(a, b, c)) == M + gains


def test_edges_without_change_give_no_row():
    genes = frozenset({0, 1})
    tree = Node(genes).add(Node(genes)).add(Node(frozenset({0})))
    assert loss_matrix(tree, families=(0, 1)) == [[0, 1]]


def test_x_marks_families_absent_from_the_context():
    # Nested loss: root {0,1,2} → {0,1} → {0}. The second parent lacks 2.
    tree = Node(frozenset({0, 1, 2})).add(Node(frozenset({0, 1})).add(Node(frozenset({0}))))
    M = loss_matrix(tree, families=(0, 1, 2))
    assert M[0] == [0, 0, 1]
    assert M[1] == [0, 1, X]


def test_gain_row_is_read_on_the_child_content():
    tree = Node(frozenset({0})).add(Node(frozenset({0, 1})))
    assert gain_matrix(tree, families=(0, 1)) == [
        [1, X],  # planted edge: gain {0} in context {0}
        [0, 1],  # gain {1} in context {0,1}
    ]


def test_contents_map_and_callable_agree():
    tree = Node("root").add(Node("leaf"))
    contents = {"root": frozenset({0, 1}), "leaf": frozenset({0})}
    assert loss_matrix(tree, contents, families=(0, 1)) == [[0, 1]]
    assert loss_matrix(tree, lambda node: contents[str(node.data)], families=(0, 1)) == [[0, 1]]


def test_block_cost_of_a_loss_matrix():
    tree = Node(frozenset({0, 1, 2})).add(Node(frozenset({0, 1}))).add(Node(frozenset({0, 2})))
    # Each of the two loss rows has a single 1: one block each.
    assert block_cost(loss_matrix(tree, families=(0, 1, 2)), [0, 1, 2]) == 2


def test_internal_node_and_two_leaves():
    assert loss_matrix(_id_tree(), _CONTENTS, families=(0, 1, 2)) == [
        [0, 0, 1],  # (ρ, u) loses c; keeps a,b
        [0, 1, X],  # (u, v) loses b; c absent from u. (u, w) has no event
    ]
    assert event_matrix(_id_tree(), _CONTENTS, families=(0, 1, 2)) == [
        [0, 0, 1],
        [0, 1, X],
        [1, 1, 1],  # planted edge: gain a,b,c
    ]


def test_contents_on_node_data():
    tree = Node(frozenset({0, 1, 2})).add(
        Node(frozenset({0, 1})).add(Node(frozenset({0}))).add(Node(frozenset({0, 1})))
    )
    assert event_matrix(tree, families=(0, 1, 2)) == event_matrix(
        _id_tree(), _CONTENTS, families=(0, 1, 2)
    )


def test_missing_node():
    incomplete = {k: v for k, v in _CONTENTS.items() if k != "w"}
    with pytest.raises(IncompleteSyntenyTreeError, match="w"):
        event_matrix(_id_tree(), incomplete)


def test_newick_labels_are_node_ids():
    newick = "((v,w)u)ρ;"
    assert event_matrix(newick, _CONTENTS, families=(0, 1, 2)) == event_matrix(
        _id_tree(), _CONTENTS, families=(0, 1, 2)
    )


def test_newick_unlabeled_internal_node_rejected():
    contents = {
        "v": frozenset({0}),
        "w": frozenset({0, 1}),
        "u": frozenset({0, 1}),
    }
    with pytest.raises(IncompleteSyntenyTreeError, match="u"):
        event_matrix("(v,w);", contents)


def test_newick_requires_a_contents_map():
    with pytest.raises(TypeError, match="Newick"):
        event_matrix("((v,w)u)ρ;")


def test_matrix_feeds_both_solvers():
    M = event_matrix(_id_tree(), _CONTENTS, families=(0, 1, 2))
    satisfiable, _ = sc1p.solve(M, solver="brute_force")
    assert satisfiable
    assert scbm.solve(M, solver="brute_force").cost == 3


def test_figure_1_of_the_paper():
    tree, x = _figure_1()
    families = tuple("abcdefghi")
    assert len(loss_matrix(tree, x, families=families)) == 4  # λ, edges 4, 7, 8, 9
    assert len(gain_matrix(tree, x, families=families)) == 4  # γ, edges 1, 2, 3, 4
    M = event_matrix(tree, x, families=families)
    assert block_lower_bound(M) == 8
    alphabetical = list(range(9))
    pi_star = [families.index(g) for g in "afedcihbg"]
    assert block_cost(M, alphabetical) == 11
    assert block_cost(M, pi_star) == 8
    assert sc1p.solve(M, solver="sat").satisfiable
    assert scbm.solve(M, solver="maxsat").cost == 8


def test_single_origin():
    tree, x = _figure_1()
    assert is_single_origin(tree, x)
    # b is gained on both edges below the root.
    twice = Node(frozenset("a")).add(Node(frozenset("ab"))).add(Node(frozenset("ab")))
    assert not is_single_origin(twice)
    with pytest.raises(NotSingleOriginError, match="occurrence_expansion"):
        event_matrix(twice)


def test_occurrence_expansion():
    twice = Node(frozenset("a")).add(Node(frozenset("ab")).add(Node(frozenset("b"))))
    twice = twice.add(Node(frozenset("ab")))
    expanded = occurrence_expansion(twice)
    # Edges: 1 planted, 2 and 4 below the root, 3 below edge 2.
    assert expanded.data == {("a", 1)}
    children = [edge.node for edge in expanded.edges]
    assert children[0].data == {("a", 1), ("b", 2)}
    assert children[0].edges[0].node.data == {("b", 2)}
    assert children[1].data == {("a", 1), ("b", 4)}
    assert is_single_origin(expanded)
    assert len(loss_matrix(expanded)) == len(loss_matrix(twice))
    assert len(gain_matrix(expanded)) == len(gain_matrix(twice))
    assert len(event_matrix(expanded)[0]) == 3  # one column per occurrence


def test_occurrence_expansion_keeps_single_origin_trees():
    tree, x = _figure_1()
    expanded = occurrence_expansion(tree, x)
    occurrences = sorted(_occurrences(expanded))
    families = [family for family, _ in occurrences]
    assert families == list("abcdefghi")  # one occurrence per family
    assert event_matrix(expanded, families=occurrences) == event_matrix(tree, x, families=families)


def _occurrences(node: Node) -> set[tuple[str, int]]:
    found: set[tuple[str, int]] = set(node.data or ())
    for edge in node.edges:
        found |= _occurrences(edge.node)
    return found
