import itertools, re
import PySpice.Logging.Logging as Logging
from PySpice.Spice.Netlist import Circuit
from PySpice.Unit import *

Logging.setup_logging()

def empty_ir(title="Candidate"):
    return {"title": title, "nodes": ["in","out","0"], "components": []}

def add_vin_and_load(ir, ac=1.0, Rload=10e3):
    # AC=1 V small-signal source recorded in IR
    ir["components"].append({"kind":"VAC","name":"in", "pos":"in","neg":"0","ac": ac})
    # Tiny "wire" placeholder for in->out path (a rewire anchor for series insertions)
    ir["components"].append({"kind":"R","name":"Rpath","n1":"in","n2":"out","value":1e-6})
    # Output load
    ir["components"].append({"kind":"R","name":"Rload","n1":"out","n2":"0","value": Rload})

from PySpice.Spice.Netlist import Circuit
from PySpice.Unit import *

def emit_pyspice(ir: dict) -> Circuit:
    """
    Convert an IR dictionary into a PySpice Circuit.
    Supports R, C, L, and VAC (AC source).
    """
    c = Circuit(ir["title"])

    for comp in ir["components"]:
        k = comp["kind"].upper()

        if k == "R":
            c.R(comp["name"], comp["n1"], comp["n2"], float(comp["value"]) @ u_Ohm)

        elif k == "C":
            c.C(comp["name"], comp["n1"], comp["n2"], float(comp["value"]) @ u_F)

        elif k == "L":
            c.L(comp["name"], comp["n1"], comp["n2"], float(comp["value"]) @ u_H)

        elif k == "VAC":
            ac_amp = float(comp["ac"])
            # Preferred: if your PySpice has AcVoltageSource
            if hasattr(c, "AcVoltageSource"):
                c.AcVoltageSource(
                    comp["name"], comp["pos"], comp["neg"], amplitude=ac_amp @ u_V
                )
            else:
                # Fallback: a source with "dc 0 ac <amp>" string works in SPICE
                c.V(comp["name"], comp["pos"], comp["neg"], f"dc 0 ac {ac_amp}")

        else:
            raise ValueError(f"Unsupported kind: {k}")

    return c

def add_series(ir, name, kind, value):
    """
    Insert a series element along the in->out path by progressively
    extending the chain of intermediate nodes.
    """
    # Make a unique new node name
    next_idx = sum(1 for c in ir["components"] if c["kind"] in ("R","C","L"))
    new_node = f"n{next_idx}"

    # Find the last element feeding 'out' and redirect it to new_node
    for comp in ir["components"]:
        if comp.get("n2") == "out":   # safe lookup
            comp["n2"] = new_node
            break

    # Append the new element from new_node to out
    ir["components"].append({
        "kind": kind,
        "name": name,
        "n1": new_node,
        "n2": "out",
        "value": value
    })

""" def add_series(ir, name, kind, value):
    # Make a unique new node label tied to current part count
    next_idx = sum(1 for c in ir["components"] if c["kind"] in ("R","C","L"))
    new_node = f"n{next_idx}"
    # Redirect Rpath end to the new node
    for comp in ir["components"]:
        if comp["name"] == "Rpath":
            comp["n2"] = new_node
            break
    # Place the new element from new_node to 'out'
    ir["components"].append({"kind":kind, "name":name, "n1":new_node, "n2":"out", "value":value}) """

def add_shunt(ir, name, kind, value, node="out"):
    """
    Insert a shunt element from 'node' down to ground (0).
    Works safely even if the IR has components like VAC
    that don’t use n1/n2 keys.
    """
    ir["components"].append({
        "kind": kind,
        "name": name,
        "n1": node,
        "n2": "0",      # SPICE convention: ground
        "value": value
    })

R_VALUES = [1e3]
C_VALUES = [160e-9]
L_VALUES = [160e-3]

def pick_value(kind, step):
    if kind == "R": return R_VALUES[step % len(R_VALUES)]
    if kind == "C": return C_VALUES[step % len(C_VALUES)]
    if kind == "L": return L_VALUES[step % len(L_VALUES)]
    raise ValueError(kind)

OPS   = ["series","shunt"]
# Allow all part kinds for both ops; tweak if you want stricter RC/LC only
KINDS = {"series":["R","L","C"], "shunt":["R","C","L"]}

def build_candidate(seq_ops, seq_kinds):
    ir = empty_ir("Candidate")
    add_vin_and_load(ir, ac=1.0, Rload=10e3)
    for step, (op, kind) in enumerate(zip(seq_ops, seq_kinds), start=1):
        val = pick_value(kind, step-1)
        if op == "series":
            add_series(ir, f"{kind}{step}", kind, val)
        else:
            add_shunt(ir, f"{kind}{step}", kind, val, node="out")
    return ir

def enumerate_all(max_steps=2):
    all_circuits = []
    for ops in itertools.product(OPS, repeat=max_steps):
        choice_lists = [KINDS[o] for o in ops]
        for kinds in itertools.product(*choice_lists):
            ir  = build_candidate(ops, kinds)
            ckt = emit_pyspice(ir)
            all_circuits.append({"ops":ops, "kinds":kinds, "ir":ir, "circuit":ckt})
    return all_circuits

def save_all_to_one(cands, filename="all_candidates.txt"):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"Total candidates: {len(cands)}\n\n")
        for i, c in enumerate(cands, 1):
            ops_str   = "->".join(c["ops"])
            kinds_str = " ".join(c["kinds"])
            f.write(f"=== Candidate {i} ===\n")
            f.write(f"ops:   {ops_str}\n")
            f.write(f"kinds: {kinds_str}\n")


            f.write("\n")
    print(f"All candidates written to {filename}")

if __name__ == "__main__":
    cands = enumerate_all(max_steps=2)         # generate everything (no simulation)
    save_all_to_one(cands, "all_candidates.txt")

import math, numpy as np

def ac_response(circuit, fstart=10, fstop=1e6, points=401):
    """Run AC sweep and return frequency [Hz], |Vout|, phase[Vout] in radians."""
    sim = circuit.simulator(temperature=25)
    ac  = sim.ac(start_frequency=fstart@u_Hz, stop_frequency=fstop@u_Hz,
                 number_of_points=points, variation='dec')
    freqs = np.array(ac.frequency, dtype=float)
    vout  = np.array(ac['out'])
    mag   = np.abs(vout)
    phase = np.angle(vout)  # radians
    return freqs, mag, phase

def estimate_fc(freqs, mag):
    """Estimate -3 dB cutoff relative to low-frequency gain (median of first few points)."""
    if len(mag) < 5:
        return np.nan, np.nan
    g0 = float(np.median(mag[:5]))
    target = g0 / math.sqrt(2)
    idx = int(np.argmin(np.abs(mag - target)))
    return float(freqs[idx]), g0

def high_freq_slope_db_per_dec(freqs, mag, top_frac=0.25):
    """
    Fit slope of 20*log10(|H|) vs log10(f) over the top 'top_frac' of the sweep.
    For 1st-order LPF, expect about -20 dB/dec.
    """
    n = len(freqs)
    start = max(0, int(n*(1-top_frac)))
    fseg = freqs[start:]
    mseg = mag[start:]
    y = 20*np.log10(np.maximum(mseg, 1e-18))
    x = np.log10(fseg)
    A = np.vstack([x, np.ones_like(x)]).T
    slope, intercept = np.linalg.lstsq(A, y, rcond=None)[0]
    return float(slope)  # dB/dec

def is_basic_lowpass(freqs, mag, phase,
                     min_drop_db=6.0, slope_target=-20.0, slope_tol=10.0, ripple_tol_db=1.0):
    """
    Lightweight classifier:
      - high freq falls by at least ~6 dB vs low freq
      - high-freq slope roughly -20 dB/dec ± tolerance
      - response mostly non-increasing (allow small ripples)
    """
    if len(mag) < 8:
        return False

    g0 = float(np.median(mag[:5]))
    gH = float(np.median(mag[-5:]))
    if 20*np.log10(max(g0,1e-18)) - 20*np.log10(max(gH,1e-18)) < min_drop_db:
        return False

    slope = high_freq_slope_db_per_dec(freqs, mag)
    if not (slope_target - slope_tol <= slope <= slope_target + slope_tol):
        return False

    mags_db = 20*np.log10(np.maximum(mag, 1e-18))
    diffs = np.diff(mags_db)
    if np.sum(diffs > ripple_tol_db) > 0:
        return False

    return True

def is_basic_lowpass(freqs, mag, phase,
                     min_drop_db=6.0, slope_target=-20.0, slope_tol=10.0, ripple_tol_db=1.0):
    """
    Lightweight classifier:
      - high freq falls by at least ~6 dB vs low freq
      - high-freq slope roughly -20 dB/dec ± tolerance
      - response mostly non-increasing (allow small ripples)
    """
    if len(mag) < 8:
        return False

    g0 = float(np.median(mag[:5]))
    gH = float(np.median(mag[-5:]))
    if 20*np.log10(max(g0,1e-18)) - 20*np.log10(max(gH,1e-18)) < min_drop_db:
        return False

    slope = high_freq_slope_db_per_dec(freqs, mag)
    if not (slope_target - slope_tol <= slope <= slope_target + slope_tol):
        return False

    mags_db = 20*np.log10(np.maximum(mag, 1e-18))
    diffs = np.diff(mags_db)
    if np.sum(diffs > ripple_tol_db) > 0:
        return False

    return True

def save_results_to_text(results, filename="simulation_results.txt"):
    """
    Save simulation results (from simulate_all) into a human-readable text file.
    """
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"Total candidates: {len(results)}\n\n")

        for r in results:
            f.write(f"Candidate {r['index']}\n")
            f.write(f"ops:   {'->'.join(r['ops'])}\n")
            f.write(f"kinds: {' '.join(r['kinds'])}\n")

            if "error" in r:
                f.write(f"ERROR: {r['error']}\n\n")
                continue

            f.write(f"fc_est ≈ {r['fc_est']:.1f} Hz\n")
            f.write(f"low-freq gain g0 = {r['g0']:.3f}\n")
            f.write(f"slope ≈ {r['slope_db_per_dec']:.1f} dB/dec\n")
            f.write(f"is_lowpass = {r['is_lowpass']}\n")

            f.write("--- Components ---\n")
            for comp in r["ir"]["components"]:
                n1 = comp.get("n1", comp.get("pos", ""))
                n2 = comp.get("n2", comp.get("neg", ""))
                val = comp.get("value", comp.get("ac", ""))
                name = comp.get("name", "")
                kind = comp.get("kind", "")
                f.write(f"{kind}{name} : {n1} -> {n2}  value={val}\n")
            f.write("\n")

    print(f"Results written to {filename}")


cands = enumerate_all(max_steps=2)
results = simulate_all(cands)
save_results_to_text(results, "all_candidates.txt")