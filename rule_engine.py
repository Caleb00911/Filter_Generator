"""Filter candidate generator and netlist emitter.

This script:
1) Builds a stage graph for an Nth-order low-pass filter.
2) Enumerates filter family assignments (Butterworth / 3 dB Chebyshev).
3) Merges adjacent stages with matching family into higher-order blocks.
4) Assigns circuit topologies to those blocks.
5) Emits concrete PySpice circuits from the resulting candidates.
"""

# ideas: implement rewrite to combine stages

import itertools, re
import PySpice.Logging.Logging as Logging
from PySpice.Spice.Netlist import Circuit
from PySpice.Spice.Netlist import SubCircuitFactory
from PySpice.Unit import *
import math
from scipy.signal import *
import cmath
from typing import *

topologies = ['Sallen-Key_LP']
types = ['Butterworth', '3dbCheb']


class Graph:
    """Minimal directed graph with mutable node/edge attributes."""
    def __init__(self):
        self.nodes = {}
        self.edges = []

    def add_node(self, name, **attrs):
        self.nodes[name] = attrs

    def add_edge(self, src, dst, **attrs):
        self.edges.append((src, dst, attrs))

    def copy(self):
        g2 = Graph()
        g2.nodes = {k: v.copy() for k, v in self.nodes.items()}
        g2.edges = [(s, d, a.copy()) for (s, d, a) in self.edges]
        return g2

    def __repr__(self):
        return f"Graph(nodes={self.nodes}, edges={self.edges})"
    
    def remove_node(self, node):
        if node in self.nodes:
            del self.nodes[node]
        self.edges = [(s, d, a) for (s, d, a) in self.edges if s != node and d != node]
    
    def succs(self, node):
    # [(dst, attrs), ...] for edges node -> dst
        return [(d, a) for (s, d, a) in self.edges if s == node]

    def preds(self, node):
    # [(src, attrs), ...] for edges src -> node
        return [(s, a) for (s, d, a) in self.edges if d == node]

    def combine(self, n1, n2):
        # Merge two connected stage nodes into n1 (order adds, type is preserved).
        in_edges = self.preds(n1)
        out_edges = self.succs(n2)

        a1 = self.nodes[n1]
        a2 = self.nodes[n2]
        merged = {
            'type' : a1.get('type'),
            'order': a1.get('order') + a2.get('order')
        }

        if a1.get("type") == a2.get("type"):
            merged["type"] = a1.get("type")
        #if a1.get("Topology") == a2.get("Topology"):
            #merged["Topology"] = a1.get("Topology")
        
        self.edges = [(s, d, a) for (s, d, a) in self.edges if s not in (n1, n2) and d not in (n1, n2)]
        self.nodes[n1] = merged
        self.remove_node(n2)

        for p, a in in_edges:
            if p != n2:  # avoid recreating the internal edge n2->n1
                self.add_edge(p, n1, **a)
        for s, a in out_edges:
            if s != n1:  # avoid self-loop
                self.add_edge(n1, s, **a)

    def combine_types(self):
        # Repeatedly merge adjacent stages when both share the same filter family.
        merges = 0
        changed = True
        while changed:
            changed = False
            for(u, v, eattrs) in list(self.edges):
                nu, nv = self.nodes[u], self.nodes[v]
                if(nu.get('type') == nv.get('type')):
                    self.combine(u, v)
                    merges += 1
                    changed = True
                    break
        return merges
    
def apply_types(g, n):
    # Generate all possible type assignments across n stages.
    type_results = []
    for i in itertools.product(types, repeat = n):
        cand = g.copy()
        for j in range(len(i)):
            stage = f"Stage{j+1}"
            cand.nodes[stage]["type"] = i[j]
        type_results.append(cand)
    return type_results


def apply_topologies(types):
    # For each type-assigned graph, generate all topology combinations.
    results = []
    for graph in types:
        stages = [n for n in graph.nodes if n != 'load']
        for combo in itertools.product(topologies, repeat = len(stages)):
            cand = graph.copy()
            for stage, topo in zip(stages, combo):
                cand.nodes[stage]['topology'] = topo
            results.append(cand)
    return results

def rule_base(g, n, load):
    # Base grammar rule: terminal load node.
    g.add_node(load, type='load')
    return load

def rule_cascade(g, n, load):
    # Recursive grammar rule: prepend a StageN before the previous chain.
    prev = apply_rule(g, n - 1, load)
    stage = f"Stage{n}"
    g.add_node(stage, order = 1)
    cascade(g, stage, prev)
    return stage

def cascade(g, c1, c2):
        # Connect one stage output into the next stage input.
        g.add_edge(c1, c2)
        return c2

def apply_rule(g, n, load):
    # Recursive dispatcher for building a linear stage cascade.
    if n == 0:
        return rule_base(g, n, load)
    else:
        return rule_cascade(g, n, load)

    
# TODO: possibly remove; acts as a validity filter on generated candidates.
def del_mismatch(graphs):
    keep = []
    for graph in graphs:
        ok = True
        for node_name, attrs in graph.nodes.items():
            if attrs.get('type') != 'Butterworth' and attrs.get('order', 0) < 2 and attrs.get('type') != 'load':
                ok = False
                break
        if ok:
            keep.append(graph)
    return keep



class RC_LP(SubCircuitFactory):
    """First-order active RC low-pass stage (buffered)."""
    NAME = 'RC_LP'
    NODES = ('input', 'out', '0')
    def __init__(self, R1, C1, gain = 1e6):
        super().__init__()
        n1 = 'n1'

        self.R(1, 'input', n1, R1)

        self.C(1, n1, '0', C1)

        self.VCVS(1, 'out', '0', n1, 'out', gain)

class SALLEN_KEY_LP(SubCircuitFactory):
    """Second-order Sallen-Key low-pass stage."""
    NAME = 'SALLEN_KEY_LP'
    NODES = ('input', 'out', '0')

    def __init__(self, R1, R2, R3, R4,  C1, C2, gain = 1e6):
        super().__init__()
        n1 = 'n1'
        n2 = 'n2'
        n3 = 'n3'

        self.R(1, 'input', n1, R1)
        self.R(2, n1, n2, R2)
        self.R(3, n3, '0', R3)
        self.R(4, n3, 'out', R4)

        self.C(1, n1, 'out', C1)
        self.C(2, n2, '0', C2)

        self.VCVS(1, 'out', '0', n2, n3, gain)


def emit(graphs):
    # Convert abstract stage graphs into concrete PySpice circuit candidates.
    results = []
    cand = 1
    for graph in graphs:
        o = 1
        count = 1
        circuit = Circuit(f'Candidate{cand}')
        circuit.V('input', 'n1', '0', 'dc 0 ac 1')      
        for node in graph.nodes:
            attrs = graph.nodes[node]
            order = attrs.get('order')
            topo = attrs.get('topology')
            type = attrs.get('type')
            stages = []
            if order == 1:
                # First-order block is emitted as RC_LP.
                vals = design_rc_lp(1000, 1, 10e-9)
                rc_name = f'RC_LP_{cand}_{count}'
                RC_LP.NAME = rc_name
                rc_subckt = RC_LP(
                    R1 = vals.get('R1'),
                    C1 = vals.get('C1')
                )
                circuit.subcircuit(rc_subckt)
                circuit.X(f'{count}', rc_name, f'n{o}', f'n{o+1}', '0')
                count += 1
                o += 1
            elif(topo == 'Sallen-Key_LP'):
                # Higher-order blocks are decomposed into 2nd-order sections (+ optional 1st-order tail).
                if(type == '3dbCheb'):
                    stages = design_chebyshev_type1(order, 1000)
                elif(type == 'Butterworth'):
                    stages = design_butterworth(order, 1000)
                for stage in stages:
                    if(stage[1] != None):
                        # 2nd-order section: use Sallen-Key with section fsf/Q.
                        vals = design_lp_sallen(stage[0], 1000, stage[1], 10e-9)
                        sk_name = f'SALLEN_KEY_LP_{cand}_{count}'
                        SALLEN_KEY_LP.NAME = sk_name


                        sk_subckt = SALLEN_KEY_LP(
                            R1 = vals.get('R1'),
                            R2 = vals.get('R2'),
                            R3 = vals.get('R3'),
                            R4 = vals.get('R4'),
                            C1 = vals.get('C1'),
                            C2 = vals.get('C2')
                        )

                        circuit.subcircuit(sk_subckt)
                        circuit.X(f'{count}', sk_name, f'n{o}', f'n{o+1}', '0')
                        count += 1
                        o += 1
                    elif(stage[1] == None):
                        # Odd-order remainder: single-pole RC section.
                        vals = design_rc_lp(1000, stage[0], 10e-9)
                        rc_name = f'RC_LP_{cand}_{count}'
                        RC_LP.NAME = rc_name

                        rc_subckt = RC_LP(
                            R1 = vals.get('R1'),
                            C1 = vals.get('C1')
                        )

                        circuit.subcircuit(rc_subckt)
                        circuit.X(f'{count}', rc_name, f'n{o}', f'n{o+1}', '0')
                        count += 1
                        o += 1
        results.append(circuit)
        cand+=1
    return results

# def cheb3b_stage_specs(order):
#     # Return normalized section specs for a given Chebyshev order.
#     stages = []
#     for fsf, q in cheb_3db_table[order]:
#         stages.append((fsf, q))
#     return stages

# def butterworth_stage_specs(order):
#     # Return normalized section specs for a given Butterworth order.
#     stages = []
#     for fsf, q in butterworth_table[order]:
#         stages.append((fsf, q))
#     return stages

def design_lp_sallen(fsf, fc, Q, C_val):
    # Compute equal-C Sallen-Key component values from section specs.
    f0 = fsf * fc
    C1 = C2 = C_val
    R = 1 / (2 * math.pi * C_val * f0)

    K = 3-(1/Q)

    # k = 1 + r3/r4
    R4 = 1000
    R3 = R4 / (K - 1)

    return {
        'R1': R,
        'R2': R,
        'R3' : R3,
        'R4' : R4,
        'C1' : C1,
        'C2' : C2,
    }

def design_butterworth(N, fc):
    wc = 2*math.pi*fc
    z, p, k = butter(N, wc, btype='low', analog=True, output='zpk')
    return zpk_to_sections_fsf_Q(p)

def design_chebyshev_type1(N, fc):
    rp = 3
    wc = 2*math.pi*fc
    z, p, k = cheby1(N, rp, wc, btype='low', analog=True, output='zpk')
    return zpk_to_sections_fsf_Q(p)

def zpk_to_sections_fsf_Q(poles) -> List[Tuple[float, Optional[float]]]:
    poles = list(poles)
    used = [False]*len(poles)
    out = []

    for i, p in enumerate(poles):
        if used[i]:
            continue
        if abs(p.imag) < 1e-12:
            out.append((abs(p.real), None))
            used[i] = True
        else:
            # find conjugate
            target = p.conjugate()
            j = min(
                (j for j in range(len(poles)) if not used[j] and j != i),
                key=lambda j: abs(poles[j] - target)
            )
            used[i] = used[j] = True

            w0 = abs(p)               # |p|  (rad/s if poles are analog)
            Q = w0 / (-2.0 * p.real)  # p.real < 0
            out.append((w0, Q))

    # optional sorting: low-Q first
    biq = sorted([s for s in out if s[1] is not None], key=lambda x: x[1])
    fo  = [s for s in out if s[1] is None]
    return biq + fo

def design_rc_lp(fc, fsf, C_val):
    # Compute single-pole RC values from cutoff and scaling factor.
    f0 = fsf * fc
    C1 = C_val
    R1 = 1 / (2*math.pi*C_val*f0)

    return{
        'R1': R1,
        'C1': C1
    }


G = Graph()
load = 'load'
# Build an 8-stage abstract cascade.
apply_rule(G, 8, load)
# Enumerate all family assignments for those 8 stages.
type_results = apply_types(G, 8)
for i in range(len(type_results)):
    # Collapse adjacent identical-family stages into combined higher-order nodes.
    type_results[i].combine_types()


results = apply_topologies(type_results)
#print (results[67].nodes)

# Remove candidates that violate the current stage/order constraints.
p = del_mismatch(results)

print(p[27].nodes)

circuits = emit(p)

print(circuits[27])

# print(len(p))
# print(p[42].nodes)
# print(G.nodes)
# print(len(type_results))
# results = apply_topologies(type_results, 4)
# print(len(results))


