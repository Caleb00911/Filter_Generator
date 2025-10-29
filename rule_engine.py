
import itertools, re

topologies = ['Sallen', 'RC', 'Ladder']

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

def topo_combos(g, n):
    results = []
    for i in itertools.product(topologies, repeat = n):
        cand = g.copy()
        for j in range(len(i)):
            stage = f"Stage{j+1}"
            cand.nodes[stage]["Topology"] = i[j]
        results.append(cand)
    return results

def rule_base(g, n, load):
    g.add_node(load, type='load')
    return load

def rule_cascade(g, n, load):
    prev = apply_rule(g, n - 1, load)
    stage = f"Stage{n}"
    g.add_node(stage, type='filter')
    cascade(g, stage, prev)
    return stage

#def rule_apply_topology(g, stage_name, topologies):
    #g.nodes[stage_name]['Topology'] = topologies

def cascade(g, c1, c2):
        g.add_edge(c1, c2)
        return c2

def apply_rule(g, n, load):
    if n == 0:
        return rule_base(g, n, load)
    else:
        return rule_cascade(g, n, load)

G = Graph()
load = 'load'
apply_rule(G, 4, load)
results = topo_combos(G, 4)
print(len(results))
print(results[20])