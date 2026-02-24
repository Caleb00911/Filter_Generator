"""Command-line interface for filter candidate generation."""

import argparse
from pathlib import Path

from .pipeline import run_pipeline


def make_parser():
    parser = argparse.ArgumentParser(
        description="Generate low-pass filter candidates and emit PySpice circuits."
    )
    parser.add_argument("--order", type=int, default=8, help="Base cascade order.")
    parser.add_argument("--fc", type=float, default=1000.0, help="Cutoff frequency in Hz.")
    parser.add_argument("--cval", type=float, default=10e-9, help="Capacitance value in F.")
    parser.add_argument(
        "--candidate-index",
        type=int,
        default=1,
        help="Candidate index to print (0-based).",
    )
    parser.add_argument(
        "--emit-out",
        type=str,
        default="out/netlist.txt",
        help="Write ALL emitted circuit netlists to this file (default: out/netlist.txt).",
    )
    return parser


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)

    candidates, circuits = run_pipeline(order=args.order, fc=args.fc, c_val=args.cval)
    if not candidates:
        print("No candidates generated.")
        return 0

    if args.emit_out:
        out_path = Path(args.emit_out).expanduser()
        if out_path.parent and not out_path.parent.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)

        with out_path.open("w", encoding="utf-8") as f:
            for i, (cand, circ) in enumerate(zip(candidates, circuits)):
                f.write(f"### Candidate {i}\n")
                f.write(f"{cand.nodes}\n\n")
                f.write(str(circ))
                f.write("\n\n")
                f.write("=" * 80)
                f.write("\n\n")

    if args.candidate_index < 0 or args.candidate_index >= len(candidates):
        print(f"Candidate index out of range. Valid: 0..{len(candidates) - 1}")
        return 1

    idx = args.candidate_index
    print(candidates[idx].nodes)
    print(circuits[idx])
    return 0
