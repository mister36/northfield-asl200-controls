# AGENTS.md

Guidance for engineers and coding agents working in this repo.

## Build and test

```bash
pip install -r requirements.txt
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j
ctest --test-dir build --output-on-failure          # C unit tests
make cppcheck                                        # static analysis (must stay clean)
python3 -m pytest tests/sil -q                       # SIL matrix (all variants x scenarios)
python3 -m pytest tests/sil -q --variant asl200_electric_mack --scenario hot    # subset
```

Rebuild (`cmake --build build`) after editing anything in `firmware/` or `variants/`: the SIL loads
the compiled libraries and the generated parameter blobs from `build/`.

## Run one scenario

```bash
python3 -m sil.runner --variant asl200_electric_mack --scenario normal       # prints checks
python3 -m sil.matrix --variant asl200_electric_mack                          # traces + PNGs + summary
```

Outputs: `out/<variant>/<scenario>.trace.json` (viewer input), `.png` (trajectory plot),
`.result.json` (checks). `python3 viz/build.py --out out` writes `out/matrix.html`.
Scenarios are defined in `sil/scenarios.py`, checks in `sil/checks.py`. A scenario can be limited
to some variants with `variants=(...)`; `None` means all.

## Replay a field log

```bash
tools/decode_dtc.py --log field_logs/<log>          # what faults were active, when
tools/replay_log.py field_logs/<log> --variant <v> --viz --plot
```

Replay runs two ways: open-loop (logged input frames → current firmware, compared frame-by-frame with
what the field ECU sent) and closed-loop (the log's conditions and operator inputs re-simulated with
the plant). `--viz` writes `out/replay/*.field.trace.json` and `*.resim.trace.json`; build a
side-by-side viewer with `python3 viz/build.py --traces A B --html out/replay/x.html`.
See `.agents/skills/triage-field-log/SKILL.md` for the full triage procedure.

## Conventions

- Firmware is C99, no dynamic allocation, no floating `double`, every tunable comes from `params_t`.
  Never hard-code a threshold in C; add it to `variants/common.yaml` + `variants/schema.json`.
- Variant differences live in the variant YAML, not in `#ifdef`s or test special cases.
- A hardware revision that changes sensor scaling or fault thresholds is a variant selection
  (`lift_sensor` in the variant YAML, catalogued in `variants/sensors.yaml`) — firmware reads the
  calibration from `params_t`; never hard-code a sensor's voltage range in C.
- Interlocks are one function each in `firmware/src/interlocks.c`.
- New DTCs: `firmware/include/faults.h`, `can/faults.yaml`, `docs/faults.md`.
- CAN changes: `can/asl200.dbc`, `firmware/src/can_io.c`, `docs/io-map.md`, and the unit test in
  `tests/unit/test_can_io.c` must change together.
- A field bug gets a regression scenario (or test built from the replayed log) that fails before the fix.
- Don't weaken a check or narrow a scenario's variant list to make CI green.
- Commit messages: imperative, reference the ticket (`ASLCTL-123`).
