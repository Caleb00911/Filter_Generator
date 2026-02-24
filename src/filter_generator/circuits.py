"""PySpice circuit blocks and netlist emission."""

from PySpice.Spice.Netlist import Circuit
from PySpice.Spice.Netlist import SubCircuitFactory

from .design import (
    design_butterworth,
    design_chebyshev_type1,
    design_lp_sallen,
    design_rc_lp,
)


class RC_LP(SubCircuitFactory):
    """First-order active RC low-pass stage (buffered)."""

    NAME = "RC_LP"
    NODES = ("input", "out", "0")

    def __init__(self, r1, c1, gain=1e6):
        super().__init__()
        n1 = "n1"

        self.R(1, "input", n1, r1)
        self.C(1, n1, "0", c1)
        self.VCVS(1, "out", "0", n1, "out", gain)


class SALLEN_KEY_LP(SubCircuitFactory):
    """Second-order Sallen-Key low-pass stage."""

    NAME = "SALLEN_KEY_LP"
    NODES = ("input", "out", "0")

    def __init__(self, r1, r2, r3, r4, c1, c2, gain=1e6):
        super().__init__()
        n1 = "n1"
        n2 = "n2"
        n3 = "n3"

        self.R(1, "input", n1, r1)
        self.R(2, n1, n2, r2)
        self.R(3, n3, "0", r3)
        self.R(4, n3, "out", r4)

        self.C(1, n1, "out", c1)
        self.C(2, n2, "0", c2)
        self.VCVS(1, "out", "0", n2, n3, gain)


def emit(graphs, fc=1000, c_val=10e-9):
    # Convert abstract stage graphs into concrete PySpice circuit candidates.
    results = []
    candidate_idx = 1
    for graph in graphs:
        node_idx = 1
        subckt_idx = 1
        circuit = Circuit(f"Candidate{candidate_idx}")
        circuit.V("input", "n1", "0", "dc 0 ac 1")

        for node in graph.nodes:
            attrs = graph.nodes[node]
            order = attrs.get("order")
            topo = attrs.get("topology")
            filter_type = attrs.get("type")
            stages = []

            if order == 1:
                vals = design_rc_lp(fc, 1, c_val)
                rc_name = f"RC_LP_{candidate_idx}_{subckt_idx}"
                RC_LP.NAME = rc_name
                rc_subckt = RC_LP(r1=vals.get("R1"), c1=vals.get("C1"))
                circuit.subcircuit(rc_subckt)
                circuit.X(f"{subckt_idx}", rc_name, f"n{node_idx}", f"n{node_idx + 1}", "0")
                subckt_idx += 1
                node_idx += 1
            elif topo == "Sallen-Key_LP":
                if filter_type == "3dbCheb":
                    stages = design_chebyshev_type1(order, fc)
                elif filter_type == "Butterworth":
                    stages = design_butterworth(order, fc)

                for stage in stages:
                    if stage[1] is not None:
                        vals = design_lp_sallen(stage[0], fc, stage[1], c_val)
                        sk_name = f"SALLEN_KEY_LP_{candidate_idx}_{subckt_idx}"
                        SALLEN_KEY_LP.NAME = sk_name
                        sk_subckt = SALLEN_KEY_LP(
                            r1=vals.get("R1"),
                            r2=vals.get("R2"),
                            r3=vals.get("R3"),
                            r4=vals.get("R4"),
                            c1=vals.get("C1"),
                            c2=vals.get("C2"),
                        )
                        circuit.subcircuit(sk_subckt)
                        circuit.X(
                            f"{subckt_idx}",
                            sk_name,
                            f"n{node_idx}",
                            f"n{node_idx + 1}",
                            "0",
                        )
                        subckt_idx += 1
                        node_idx += 1
                    else:
                        vals = design_rc_lp(fc, stage[0], c_val)
                        rc_name = f"RC_LP_{candidate_idx}_{subckt_idx}"
                        RC_LP.NAME = rc_name
                        rc_subckt = RC_LP(r1=vals.get("R1"), c1=vals.get("C1"))
                        circuit.subcircuit(rc_subckt)
                        circuit.X(
                            f"{subckt_idx}",
                            rc_name,
                            f"n{node_idx}",
                            f"n{node_idx + 1}",
                            "0",
                        )
                        subckt_idx += 1
                        node_idx += 1

        results.append(circuit)
        candidate_idx += 1
    return results
