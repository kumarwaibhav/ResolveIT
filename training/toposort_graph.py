"""Reorder ONNX nodes topologically, counting outer-scope names used inside subgraphs.

torch.onnx can emit an If node before the node producing a value its branch
reads from the enclosing scope. ONNX Runtime tolerates that; the official ONNX
checker does not. Reordering changes no operator, attribute or tensor, so the
computation is identical. External-data references are preserved as they are.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import onnx


def _subgraphs(node: Any) -> list[Any]:
    out = []
    for attr in node.attribute:
        if attr.HasField("g"):
            out.append(attr.g)
        out.extend(attr.graphs)
    return out


def _outer_reads(graph: Any) -> set[str]:
    """Names a (sub)graph reads that it does not define itself."""
    defined = {i.name for i in graph.input} | {i.name for i in graph.initializer}
    reads: set[str] = set()
    for node in graph.node:
        reads.update(n for n in node.input if n)
        for sub in _subgraphs(node):
            reads |= _outer_reads(sub)
        defined.update(node.output)
    reads.update(o.name for o in graph.output)
    return reads - defined


def sort_graph(graph: Any, outer: set[str]) -> int:
    """Sort graph.node in place; returns how many nodes moved. Recurses into subgraphs."""
    nodes = list(graph.node)
    available = set(outer) | {i.name for i in graph.input} | {i.name for i in graph.initializer} | {""}
    producer = {o: idx for idx, n in enumerate(nodes) for o in n.output if o}
    needs: list[set[int]] = []
    for node in nodes:
        reads = {n for n in node.input if n}
        for sub in _subgraphs(node):
            reads |= _outer_reads(sub)
        needs.append({producer[r] for r in reads if r not in available and r in producer})
    users: dict[int, list[int]] = defaultdict(list)
    for idx, deps in enumerate(needs):
        for d in deps:
            users[d].append(idx)
    pending = [len(d) for d in needs]
    ready = deque(i for i, p in enumerate(pending) if p == 0)
    order: list[int] = []
    while ready:
        i = ready.popleft()
        order.append(i)
        for u in users[i]:
            pending[u] -= 1
            if pending[u] == 0:
                ready.append(u)
    if len(order) != len(nodes):
        raise ValueError("Graph has a cycle or an input no node produces")
    moved = sum(1 for pos, i in enumerate(order) if pos != i)
    scope = set(available)
    for i in order:
        for sub in _subgraphs(nodes[i]):
            moved += sort_graph(sub, scope)
        scope.update(nodes[i].output)
    del graph.node[:]
    graph.node.extend(nodes[i] for i in order)
    return moved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--inline", action="store_true", help="source has inline weights; load them")
    args = parser.parse_args()
    model = onnx.load(str(args.source), load_external_data=args.inline)
    moved = sort_graph(model.graph, set())
    onnx.save(model, str(args.target))
    print(f"reordered {moved} nodes -> {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
