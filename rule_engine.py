#ideas: implement rewrite to combine stages


import itertools, re

topologies = ['Sallen', 'RC', 'Ladder']
types = ['Butterworth', 'Cheb1', 'Cheb2']

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
    
def apply_types(g, n):
    type_results = []
    for i in itertools.product(types, repeat = n):
        cand = g.copy()
        for j in range(len(i)):
            stage = f"Stage{j+1}"
            cand.nodes[stage]["Type"] = i[j]
        type_results.append(cand)
    return type_results

def apply_topologies(types, n):
    results = []
    #pairs = list(itertools.product(topologies, types))
    for i in itertools.product(topologies, repeat = n):
        for graph in types:
            cand = graph.copy()
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
    g.add_node(stage, type='filter', order = 1)
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

G = Graph()
load = 'load'
apply_rule(G, 4, load)
type_results = apply_types(G, 4)
print(len(type_results))
results = apply_topologies(type_results, 4)
print(len(results))