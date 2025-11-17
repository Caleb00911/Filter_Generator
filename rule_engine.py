#ideas: implement rewrite to combine stages

import itertools, re
import PySpice.Logging.Logging as Logging
from PySpice.Spice.Netlist import Circuit
from PySpice.Spice.Netlist import SubCircuitFactory
from PySpice.Unit import *

topologies = ['RC_LP', 'Sallen-Key_LP']
types = ['Butterworth', 'Cheb']

class Graph:
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
        merges = 0
        changed = True
        while changed:
            changed = False
            for(u, v, eattrs) in list(self.edges):
                nu, nv = self.nodes[u], self.nodes[v]
                if(nu.get('type') == nv.get('type') and nu.get('order') < 2 and nv.get('order') < 2):
                    self.combine(u, v)
                    merges += 1
                    changed = True
                    break
        return merges
    
def apply_types(g, n):
    type_results = []
    for i in itertools.product(types, repeat = n):
        cand = g.copy()
        for j in range(len(i)):
            stage = f"Stage{j+1}"
            cand.nodes[stage]["type"] = i[j]
        type_results.append(cand)
    return type_results


def apply_topologies(types):
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
    g.add_node(load, type='load')
    return load

def rule_cascade(g, n, load):
    prev = apply_rule(g, n - 1, load)
    stage = f"Stage{n}"
    g.add_node(stage, order = 1)
    cascade(g, stage, prev)
    return stage

def cascade(g, c1, c2):
        g.add_edge(c1, c2)
        return c2

def apply_rule(g, n, load):
    if n == 0:
        return rule_base(g, n, load)
    else:
        return rule_cascade(g, n, load)

    
    
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
    NAME = 'RC_LP'
    NODES = ('input', 'out', '0')
    def __init__(self, R, C):
        super().__init__()
        self.R(1, 'input', 'out', R)
        self.C(1, 'out', '0', C)

class SALLEN_KEY_LP(SubCircuitFactory):
    NAME = 'SALLEN_KEY_LP'
    NODES = ('input', 'out', '0')

    def __init__(self, R1, R2, C1, C2, gain = 1e6):
        super().__init__()
        n1 = 'n1'
        n2 = 'n2'

        self.R(1, 'input', n1, R1)
        self.R(2, n1, n2, R2)

        self.C(1, n1, 'out', C1)
        self.C(2, n2, '0', C2)

        self.VCVS(1, 'out', '0', n2, 'out', gain)


def emit(graphs):
    results = []
    cand = 1
    for graph in graphs:
        o = 1
        count = 1
        circuit = Circuit(f'Candidate{cand}')
        circuit.subcircuit(SALLEN_KEY_LP(
            R1=10e3,
            R2=10e3,
            C1=10e-9,
            C2=10e-9
        ))
        circuit.subcircuit(RC_LP(
            R = 10e3,
            C = 10e-9
        ))
        for node in graph.nodes:
            attrs = graph.nodes[node]
            topo = attrs.get('topology')
            if topo is None:
                continue
            if(topo == 'Sallen-Key_LP'):
                circuit.X(f'{count}', 'SALLEN_KEY_LP', f'n{o}', f'n{o+1}', '0')
                count += 1
                o += 1
            elif(topo == 'RC_LP'):
                circuit.X(f'{count}', 'RC_LP', f'n{o}', f'n{o+1}', '0')
                count += 1
                o += 1
        results.append(circuit)
        cand += 1
    return results


G = Graph()
load = 'load'
apply_rule(G, 4, load)
type_results = apply_types(G, 4)
for i in range(len(type_results)):
    type_results[i].combine_types()


results = apply_topologies(type_results)
# print (results[67].nodes)

p = del_mismatch(results)

#print(p[10].edges)

circuits = emit(p)

print(circuits[10])

# print(len(p))
# print(p[42].nodes)
# print(G.nodes)
# print(len(type_results))
# results = apply_topologies(type_results, 4)
# print(len(results))

