# Filter Generator

This project was designed to be used as a design space exploration for analog filters. It currently generates a large amount of low-pass filters given cut-off frequency and order. It currently only implements a small set of familes/topologies. In general, this project is meant to be used as a stepping stone for a full-scale analog circuit design space explorer/compiler. 

## Future Plans
- Expand the project to include all types of filters and wider variety of families/topologies.
- Design a way to explore filter topologies to reduce the need to hand design circuits. 
- Connect to SPICE simulator backend to perform simulation and comparison of different filters automatically. 

## Project layout

- `src/filter_generator/graph.py` - graph structure and stage merging
- `src/filter_generator/rules.py` - generation rules and assignment passes
- `src/filter_generator/design.py` - analog section synthesis utilities
- `src/filter_generator/circuits.py` - PySpice subcircuits and emitter
- `src/filter_generator/pipeline.py` - end-to-end build pipeline
- `src/filter_generator/cli.py` - command-line entrypoint
- `rule_engine.py` - compatibility wrapper that calls the new CLI

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run

Module form:

```bash
python -m filter_generator --order 8 --candidate-index 27
```

Write all emitted netlists to a file:

```bash
python -m filter_generator --order 8 --emit-out out/netlists.txt
```

Installed command:

```bash
filter-generator --order 8 --candidate-index 27
```
