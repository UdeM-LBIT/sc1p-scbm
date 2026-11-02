"""Event matrices of a synteny tree ``⟨T, x⟩``.

``T`` is a rooted tree and ``x`` gives the synteny (set of gene families) of
every node, root and internal nodes included; contents are never inferred from
the leaves. As in the paper, the planted tree adds a root of empty content
above ``T``, so the planted edge gains the content of the root of ``T``.

:func:`loss_matrix` and :func:`gain_matrix` build ``M⁻`` and ``M⁺``, and
:func:`event_matrix` builds the event matrix ``M``, the rows of ``M⁻``
followed by those of ``M⁺``. The matrices are ternary (``0``, ``1``, ``2`` for
``X``) and can be passed directly to ``sc1p.solve`` or ``scbm.solve``.

The reductions of the paper hold for single-origin synteny trees, in which
every family is gained on exactly one edge. For other trees,
:func:`occurrence_expansion` builds the occurrence-expanded tree, which is
single-origin and has the same loss and gain edges.

Every function takes the tree as a :class:`sowing.Node` or as a Newick string,
and the contents as one of:

- ``None``: ``node.data`` is the content ``x(v)`` itself;
- a ``{node id: content}`` map covering every node, where the node id is
  ``node.data`` or, for a Newick string, the node label;
- a callable ``Node -> content``.
"""

from __future__ import annotations

__version__ = "0.1.0"

from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from itertools import count
from typing import Any, TypeAlias

from sowing import Node
from sowing.repr.newick import parse as parse_newick

Matrix: TypeAlias = list[list[int]]
Family: TypeAlias = Hashable
Labeling: TypeAlias = Callable[[Node], AbstractSet[Family]]
Contents: TypeAlias = Mapping[Any, AbstractSet[Family]]

#: Matrix value for ``X``: the family is absent from the context of the event.
X = 2

__all__ = [
    "Contents",
    "Family",
    "IncompleteSyntenyTreeError",
    "Labeling",
    "Matrix",
    "NotSingleOriginError",
    "X",
    "event_matrix",
    "gain_matrix",
    "is_single_origin",
    "loss_matrix",
    "occurrence_expansion",
]


class IncompleteSyntenyTreeError(ValueError):
    """Raised when a node of ``T`` has no content ``x(v)``."""


class NotSingleOriginError(ValueError):
    """Raised by :func:`event_matrix` when a family is gained on several edges."""


def _edges(tree: Node) -> Iterable[tuple[Node, Node]]:
    """``(parent, child)`` pairs in depth-first, left-to-right order."""
    for edge in tree.edges:
        child = edge.node
        yield tree, child
        yield from _edges(child)


def _nodes(tree: Node) -> Iterable[Node]:
    yield tree
    for edge in tree.edges:
        yield from _nodes(edge.node)


def _newick_label(data: object) -> Hashable | None:
    if isinstance(data, Mapping) and "name" in data:
        return data["name"]
    return None


def _with_newick_labels(node: Node) -> Node:
    """Copy of *node* whose ``data`` is the Newick label, or ``None`` if unlabeled."""
    out = Node(_newick_label(node.data))
    for edge in node.edges:
        out = out.add(_with_newick_labels(edge.node))
    return out


def _reject_unlabeled_newick(tree: Node, contents: Contents) -> None:
    if not any(node.data is None for node in _nodes(tree)):
        return
    labeled = {node.data for node in _nodes(tree) if node.data is not None}
    unknown = [key for key in contents if key not in labeled]
    extra = f" Contents keys with no matching Newick label: {unknown!r}." if unknown else ""
    raise IncompleteSyntenyTreeError(
        "Newick internal nodes without labels cannot carry contents x(v). "
        "Label internal nodes in the Newick string "
        "(e.g. '(A,B)u;') or pass a sowing.Node already built." + extra
    )


def _content_from_data(node: Node) -> AbstractSet[Family]:
    data = node.data
    if isinstance(data, (str, bytes)) or not isinstance(data, AbstractSet):
        raise TypeError(
            "without a contents mapping, node.data must be "
            f"the synteny x(v); got {type(data).__name__} {data!r}"
        )
    return data


def _missing_ids(tree: Node, contents: Contents) -> list[Hashable]:
    missing: list[Hashable] = []
    for node in _nodes(tree):
        ident = node.data
        try:
            present = ident in contents
        except TypeError as exc:
            raise TypeError(
                f"node id node.data={ident!r} is not a valid mapping key; "
                "use a hashable identifier when passing a contents map"
            ) from exc
        if not present:
            missing.append(ident)
    return missing


def _require_labeling(tree: Node, contents: Labeling | Contents) -> Labeling:
    """Resolve *contents*, requiring a content for every node of *tree*."""
    if isinstance(contents, Mapping):
        missing = _missing_ids(tree, contents)
        if missing:
            raise IncompleteSyntenyTreeError(
                "contents must cover every node (root, internal nodes, "
                f"and leaves); missing: {missing!r}"
            )
        mapping = contents

        def by_data(node: Node) -> AbstractSet[Family]:
            return mapping[node.data]

        return by_data

    x = contents
    failed: list[Hashable] = []
    first_error: BaseException | None = None
    for node in _nodes(tree):
        try:
            x(node)
        except Exception as exc:  # noqa: BLE001
            failed.append(node.data)
            if first_error is None:
                first_error = exc
    if failed:
        raise IncompleteSyntenyTreeError(
            "contents must give a synteny for every node (root, internal "
            f"nodes, and leaves); failed on: {failed!r}"
        ) from first_error
    return x


def _resolve(tree: Node | str, contents: Labeling | Contents | None) -> tuple[Node, Labeling]:
    """``(T, x)`` from any accepted form of the tree and its contents."""
    if isinstance(tree, str):
        if not isinstance(contents, Mapping):
            raise TypeError(
                "a Newick string supplies node labels, not syntenies; pass "
                "contents={label: frozenset(...)} covering every node"
            )
        node = _with_newick_labels(parse_newick(tree))
        _reject_unlabeled_newick(node, contents)
    elif isinstance(tree, Node):
        node = tree
    else:
        raise TypeError(f"tree must be a sowing.Node or a Newick string; got {type(tree).__name__}")
    if contents is None:
        for v in _nodes(node):
            _content_from_data(v)
        return node, _content_from_data
    return node, _require_labeling(node, contents)


def _planted_edges(tree: Node, x: Labeling) -> list[tuple[set[Family], set[Family]]]:
    """``(x(u_i), x(v_i))`` for the edges ``e_i`` of the planted tree, starting
    with the planted edge, whose parent has empty content."""
    pairs: list[tuple[set[Family], set[Family]]] = [(set(), set(x(tree)))]
    pairs.extend((set(x(parent)), set(x(child))) for parent, child in _edges(tree))
    return pairs


def _family_order(
    tree: Node,
    x: Labeling,
    families: Sequence[Family] | None,
) -> list[Family]:
    if families is not None:
        return list(families)
    seen: list[Family] = []
    belong: set[Family] = set()
    for node in _nodes(tree):
        for gene in x(node):
            if gene not in belong:
                belong.add(gene)
                seen.append(gene)
    return seen


def _row(
    context: AbstractSet[Family],
    involved: AbstractSet[Family],
    families: Sequence[Family],
) -> list[int]:
    """``1`` on *involved*, ``0`` on the rest of *context*, ``X`` elsewhere."""
    return [1 if j in involved else 0 if j in context else X for j in families]


def loss_matrix(
    tree: Node | str,
    contents: Labeling | Contents | None = None,
    *,
    families: Sequence[Family] | None = None,
) -> Matrix:
    """Loss matrix ``M⁻``.

    One row per loss edge ``(u, v)``, i.e. with ``x(u) - x(v)`` nonempty:
    ``1`` if the family is lost on the edge, ``0`` if it is in
    ``x(u) ∩ x(v)``, ``X`` if it is not in ``x(u)``. *families* sets the
    column order, by default the order of first appearance in a depth-first
    walk.
    """
    node, x = _resolve(tree, contents)
    cols = _family_order(node, x, families)
    return [_row(xu, xu - xv, cols) for xu, xv in _planted_edges(node, x) if xu - xv]


def gain_matrix(
    tree: Node | str,
    contents: Labeling | Contents | None = None,
    *,
    families: Sequence[Family] | None = None,
) -> Matrix:
    """Gain matrix ``M⁺``.

    One row per gain edge ``(u, v)`` of the planted tree, i.e. with
    ``x(v) - x(u)`` nonempty: ``1`` if the family is gained on the edge,
    ``0`` if it is in ``x(u) ∩ x(v)``, ``X`` if it is not in ``x(v)``. The
    first row is the planted edge, which gains the content of the root.
    """
    node, x = _resolve(tree, contents)
    cols = _family_order(node, x, families)
    return [_row(xv, xv - xu, cols) for xu, xv in _planted_edges(node, x) if xv - xu]


def is_single_origin(tree: Node | str, contents: Labeling | Contents | None = None) -> bool:
    """Whether every family is gained on exactly one edge of the planted tree."""
    node, x = _resolve(tree, contents)
    gained: set[Family] = set()
    for xu, xv in _planted_edges(node, x):
        for family in xv - xu:
            if family in gained:
                return False
            gained.add(family)
    return True


def event_matrix(
    tree: Node | str,
    contents: Labeling | Contents | None = None,
    *,
    families: Sequence[Family] | None = None,
) -> Matrix:
    """Event matrix ``M``: the rows of ``M⁻`` followed by the rows of ``M⁺``.

    Raises :class:`NotSingleOriginError` if a family is gained on several
    edges; apply :func:`occurrence_expansion` to such a tree first.
    """
    node, x = _resolve(tree, contents)
    if not is_single_origin(node, x):
        raise NotSingleOriginError(
            "the synteny tree is not single-origin: some family is gained on "
            "several edges. Build the event matrix of occurrence_expansion(tree) "
            "instead, with one column per occurrence."
        )
    cols = _family_order(node, x, families)
    return loss_matrix(node, x, families=cols) + gain_matrix(node, x, families=cols)


def occurrence_expansion(tree: Node | str, contents: Labeling | Contents | None = None) -> Node:
    """Occurrence-expanded synteny tree ``T̃``.

    Each family ``g`` at a node ``v`` is relabeled by the occurrence
    ``(g, i)``, where ``e_i`` is the last edge gaining ``g`` on the path from
    the planted root to ``v``. Edges are numbered from ``1`` (the planted
    edge) in depth-first, left-to-right order, as the rows of the matrices.
    The result has the shape of *tree*, with ``node.data`` holding the
    expanded content; it is single-origin and has the same loss and gain
    edges as *tree*.
    """
    node, x = _resolve(tree, contents)
    index = count(1)

    def expand(v: Node, parent: AbstractSet[Family], origin: dict[Family, int]) -> Node:
        edge = next(index)
        content = set(x(v))
        here = {g: origin[g] if g in parent else edge for g in content}
        out = Node(frozenset((g, i) for g, i in here.items()))
        for child in v.edges:
            out = out.add(expand(child.node, content, here))
        return out

    return expand(node, set(), {})
