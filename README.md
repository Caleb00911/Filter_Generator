# Filter Generator

Generates candidate low-pass filter architectures, assigns filter families/topologies, and emits PySpice circuits.

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

Script form (backward compatible):

```bash
python rule_engine.py --order 8 --candidate-index 27
```

Installed command:

```bash
filter-generator --order 8 --candidate-index 27
```
