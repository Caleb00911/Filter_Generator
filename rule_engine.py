
#idea: add a list of rules and run through the list
#TODO: add topology rule and enumerate over multiple circuits

class Graph:
    def __init__(self):
        self.nodes = {}
        self.edges = []

    def add_node(self, name, **attrs):
        self.nodes[name] = attrs

    def add_edge(self, src, dst, **attrs):
        self.edges.append((src, dst, attrs))

def rule_base(g, n, load):
    g.add_node(load, type='load')
    return load

def rule_cascade(g, n, load):
    prev = apply_rule(g, n - 1, load)
    stage = f"Stage{n}"
    g.add_node(stage, type='filter')
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
print("Nodes: ", G.nodes)
print("Edges: ", G.edges)