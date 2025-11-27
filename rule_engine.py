#ideas: implement rewrite to combine stages

import itertools, re
import PySpice.Logging.Logging as Logging
from PySpice.Spice.Netlist import Circuit
from PySpice.Spice.Netlist import SubCircuitFactory
from PySpice.Unit import *
import math

topologies = ['Sallen-Key_LP']
types = ['Butterworth', '3dbCheb']
cheb_3db_table = cheb_table = {
    2: [(0.8414, 1.3049)],
    3: [(0.9160, 3.0678), (0.2986, None)],
    4: [(0.4426, 1.0765), (0.9503, 5.5770)],
    5: [(0.6140, 2.1380), (0.9675, 8.8111), (0.1775, None)],
    6: [(0.2980, 1.0441), (0.7224, 3.4597), (0.9771, 12.7899)],
    7: [(0.4519, 1.9821), (0.7920, 5.0193), (0.9831, 17.4929), (0.1265, None)],
    8: [(0.2228, 1.0558), (0.5665, 3.0789), (0.8388, 6.8302), (0.9870, 22.8481)],
    9: [(0.3559, 1.9278), (0.6503, 4.3179), (0.8716, 8.8756),
        (0.9897, 28.9400), (0.0983, None)],
    10: [(0.1796, 1.0289), (0.4626, 2.9350), (0.7126, 5.7012),
         (0.8954, 11.1646), (0.9916, 35.9274)]
}

butterworth_table = {
    2: [(1.0000, 0.7071)],
    
    3: [(1.0000, 1.0000),
        (1.0000, None)],
    
    4: [(1.0000, 0.5412),
        (1.0000, 1.3065)],
    
    5: [(1.0000, 0.6180),
        (1.0000, 1.6181),
        (1.0000, None)],
    
    6: [(1.0000, 0.5177),
        (1.0000, 0.7071),
        (1.0000, 1.9320)],
    
    7: [(1.0000, 0.5549),
        (1.0000, 0.8019),
        (1.0000, 2.2472),
        (1.0000, None)],
    
    8: [(1.0000, 0.5098),
        (1.0000, 0.6013),
        (1.0000, 0.8999),
        (1.0000, 2.5628)],
    
    9: [(1.0000, 0.5321),
        (1.0000, 0.6527),
        (1.0000, 1.0000),
        (1.0000, 2.8802),
        (1.0000, None)],
    
    10: [(1.0000, 0.5062),
         (1.0000, 0.5612),
         (1.0000, 0.7071),
         (1.0000, 1.1013),
         (1.0000, 3.1969)]
}

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
                if(nu.get('type') == nv.get('type')):
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

    
#maybe get rid of     
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
    def __init__(self, R1, C1, gain = 1e6):
        super().__init__()
        n1 = 'n1'

        self.R(1, 'input', n1, R1)

        self.C(1, n1, '0', C1)

        self.VCVS(1, 'out', '0', n1, 'out', gain)

class SALLEN_KEY_LP(SubCircuitFactory):
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
                if(type == '3dbCheb'):
                    stages = cheb3b_stage_specs(order)
                elif(type == 'Butterworth'):
                    stages = butterworth_stage_specs(order)
                for stage in stages:
                    if(stage[1] != None):
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



    #             if(order % 2 == 0):
    #                 cascades = order // 2
    #                 for i in range(cascades):
    #                     circuit.X(f'{count}', 'SALLEN_KEY_LP', f'n{o}', f'n{o+1}', '0')
    #                     count += 1
    #                     o += 1
    #             elif (order % 2 != 0):
    #                 cascades = order // 2
    #                 for i in range(cascades):
    #                     circuit.X(f'{count}', 'SALLEN_KEY_LP', f'n{o}', f'n{o+1}', '0')
    #                     count += 1
    #                     o += 1
    #                 circuit.X(f'{count}', 'RC_LP', f'n{o}', f'n{o+1}', '0')
    #                 count += 1
    #                 o += 1
    #         elif(topo == 'RC_LP'):
    #             for i in range(order):
    #                 circuit.X(f'{count}', 'RC_LP', f'n{o}', f'n{o+1}', '0')
    #                 count += 1
    #                 o += 1
    #     results.append(circuit)
    #     cand += 1
    # return results


def cheb3b_stage_specs(order):
    stages = []
    for fsf, q in cheb_3db_table[order]:
        stages.append((fsf, q))
    return stages

def butterworth_stage_specs(order):
    stages = []
    for fsf, q in butterworth_table[order]:
        stages.append((fsf, q))
    return stages

def design_lp_sallen(fsf, fc, Q, C_val):
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

def design_rc_lp(fc, fsf, C_val):
    f0 = fsf * fc
    C1 = C_val
    R1 = 1 / (2*math.pi*C_val*f0)

    return{
        'R1': R1,
        'C1': C1
    }


G = Graph()
load = 'load'
apply_rule(G, 8, load)
type_results = apply_types(G, 8)
for i in range(len(type_results)):
    type_results[i].combine_types()


results = apply_topologies(type_results)
# print (results[67].nodes)

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


