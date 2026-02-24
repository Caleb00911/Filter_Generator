"""Graph model for stage-cascade candidates."""


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
            "type": a1.get("type"),
            "order": a1.get("order") + a2.get("order"),
        }

        if a1.get("type") == a2.get("type"):
            merged["type"] = a1.get("type")

        self.edges = [
            (s, d, a)
            for (s, d, a) in self.edges
            if s not in (n1, n2) and d not in (n1, n2)
        ]
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
            for (u, v, _eattrs) in list(self.edges):
                nu, nv = self.nodes[u], self.nodes[v]
                if nu.get("type") == nv.get("type"):
                    self.combine(u, v)
                    merges += 1
                    changed = True
                    break
        return merges
