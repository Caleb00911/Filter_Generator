"""Generation rules for stage graphs and attribute assignment."""

import itertools

from .constants import FILTER_TYPES, TOPOLOGIES


def apply_types(graph, stage_count):
    # Generate all possible type assignments across stage_count stages.
    type_results = []
    for assignment in itertools.product(FILTER_TYPES, repeat=stage_count):
        cand = graph.copy()
        for idx, filter_type in enumerate(assignment):
            stage = f"Stage{idx + 1}"
            cand.nodes[stage]["type"] = filter_type
        type_results.append(cand)
    return type_results


def apply_topologies(type_graphs):
    # For each type-assigned graph, generate all topology combinations.
    results = []
    for graph in type_graphs:
        stages = [node for node in graph.nodes if node != "load"]
        for combo in itertools.product(TOPOLOGIES, repeat=len(stages)):
            cand = graph.copy()
            for stage, topo in zip(stages, combo):
                cand.nodes[stage]["topology"] = topo
            results.append(cand)
    return results


def rule_base(graph, _n, load):
    # Base grammar rule: terminal load node.
    graph.add_node(load, type="load")
    return load


def rule_cascade(graph, n, load):
    # Recursive grammar rule: prepend a StageN before the previous chain.
    prev = apply_rule(graph, n - 1, load)
    stage = f"Stage{n}"
    graph.add_node(stage, order=1)
    cascade(graph, stage, prev)
    return stage


def cascade(graph, stage_a, stage_b):
    # Connect one stage output into the next stage input.
    graph.add_edge(stage_a, stage_b)
    return stage_b


def apply_rule(graph, n, load):
    # Recursive dispatcher for building a linear stage cascade.
    if n == 0:
        return rule_base(graph, n, load)
    return rule_cascade(graph, n, load)


def del_mismatch(graphs):
    # Keep only candidates that satisfy current family/order constraints.
    keep = []
    for graph in graphs:
        ok = True
        for _, attrs in graph.nodes.items():
            if (
                attrs.get("type") != "Butterworth"
                and attrs.get("order", 0) < 2
                and attrs.get("type") != "load"
            ):
                ok = False
                break
        if ok:
            keep.append(graph)
    return keep
