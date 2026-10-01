# northfield-asl200-controls

Body-controller firmware for the **Northfield Body Works ASL-200 automated side-loader**
(refuse body: reach-out arm, gripper, lift/dump), plus the software-in-the-loop (SIL) harness
that tests it against a plant model over a virtual J1939 CAN bus.

> Fictional product and company, built as a demonstration repository.

```
            CAN (J1939, can/asl200.dbc)
 ┌──────────────┐   ARM_CMD / ARM_STATE / DM1    ┌───────────────────────┐
 │  firmware/   │ ─────────────────────────────▶ │  sil/plant/           │
 │  C99, 10 ms  │                                │  SimPlant (Python)    │
 │ controller_  │ ◀───────────────────────────── │  or HilRigPlant (rig) │
 │ step()       │  CCVS / AMB / JOY / sensors     └───────────────────────┘
 └──────────────┘
```

## Quick start

```bash
pip install -r requirements.txt           # cantools, python-can, matplotlib, pytest ...
make sil                                  # build + full variant x scenario matrix (~30 s)
make viz                                  # out/matrix.html dashboard + per-run animated viewers
```

Or `./scripts/run_sil.sh` (same thing). Needs CMake ≥ 3.16, a C99 compiler and Python ≥ 3.10.

| Command | What it does |
|---|---|
| `make build` | Host build: one SIL shared library per variant + host compile check of the target entry point |
| `make unit` | C unit tests (scaling, filters, interlocks, CAN codec) via CTest |
| `make cppcheck` | Static analysis (warning/style/performance/portability) |
| `make sil [VARIANT=...]` | pytest SIL matrix; traces/plots/results in `out/<variant>/<scenario>.*` |
| `python3 -m sil.runner --variant V --scenario S` | One run, prints check results, writes the trace |
| `tools/replay_log.py LOG --variant V [--viz --plot]` | Decode a candump field log and replay it through current firmware |
| `tools/decode_dtc.py SPN FMI` / `--log LOG` | J1939 DTC lookup from `can/faults.yaml` |
| `viz/viewer.html` | Offline trace viewer (open, drop one or two `*.trace.json`) |

Cross-compile for the ECU (Cortex-M4F, `arm-none-eabi-gcc`):

```bash
cmake -S . -B build-target -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi.cmake -DASL200_VARIANT=asl200_electric_mack
cmake --build build-target        # -> asl200_fw_<variant>.elf / .hex
```

## Layout

| Path | Contents |
|---|---|
| `firmware/src/` | `controller.c` (state machine), `interlocks.c`, `scaling.c`, `filters.c`, `faults.c` (DTC table), `can_io.c` (J1939 codec) |
| `firmware/sil/` | SIL shared-library entry point (`sil_step()`: CAN frames in, CAN frames out) |
| `firmware/target/` | ECU main loop + HAL hooks (cross build) |
| `variants/` | Per-variant YAML (inherits `common.yaml`), validated by `schema.json` |
| `codegen/` | YAML → `params_<variant>.h` (`params_t`) + runtime JSON blob |
| `can/` | `asl200.dbc` (J1939 message set), `faults.yaml` (SPN/FMI table) |
| `sil/` | Harness: DBC codec, ctypes ECU wrapper, virtual bus, plant models, scenarios, checks, plots |
| `tests/unit/`, `tests/sil/` | C unit tests; pytest variant × scenario matrix |
| `tools/` | Field-log replay, DTC decoder |
| `viz/` | Trace viewer, matrix dashboard, GIF renderer |
| `field_logs/` | candump logs pulled from units in the field |
| `docs/` | Architecture, I/O map, variants, faults, ECOs |

## Variants

`asl200_diesel_autocar`, `asl200_cng_peterbilt`, `asl200_electric_mack`, `asl200_diesel_mack_longreach`.
See [docs/variants.md](docs/variants.md).

## Notes

- In a CODESYS shop this module would be IEC 61131-3 Structured Text; the harness and workflow are the same.
- `HilRigPlant` (`sil/plant/hil_rig.py`) is a stub with the same interface as `SimPlant`: that is where a
  bench / HIL rig plugs in. Nothing in this repo pretends to talk to hardware.
- No functional-safety claim is made. A production program would trace requirements → tests as
  ISO 13849 / IEC 61508 evidence; the scenario checks are written to make that mapping straightforward.
- MISRA C:2012 checking (cppcheck addon) is a "would enable" item; CI runs plain cppcheck today.
