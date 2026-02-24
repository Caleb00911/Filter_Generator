"""High-level candidate generation pipeline."""

from .circuits import emit
from .graph import Graph
from .rules import apply_rule, apply_topologies, apply_types, del_mismatch


def build_candidates(order=8, load_name="load"):
    graph = Graph()
    apply_rule(graph, order, load_name)
    type_results = apply_types(graph, order)
    for candidate in type_results:
        candidate.combine_types()

    topology_results = apply_topologies(type_results)
    return del_mismatch(topology_results)


def run_pipeline(order=8, load_name="load", fc=1000, c_val=10e-9):
    candidates = build_candidates(order=order, load_name=load_name)
    circuits = emit(candidates, fc=fc, c_val=c_val)
    return candidates, circuits
