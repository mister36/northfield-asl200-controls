---
name: triage-field-log
description: Triage an ASL-200 field issue from a candump CAN log - decode, replay in SIL, reproduce, write a failing regression test, fix, and open a PR with before/after evidence. Use when a ticket or message includes a field log (field_logs/*.log, candump format) or reports an arm fault from a unit in service.
---

# Field-log triage (ASL-200)

1. **Collect the facts from the report.** Unit number, variant, ambient conditions, what the operator
   saw, how often, what cleared it. Identify the variant name in `variants/` (ask if ambiguous).
2. **Decode the faults.**
   `tools/decode_dtc.py --log <log>` lists every DM1 transition with SPN/FMI meaning and the
   corrective action from `can/faults.yaml`.
3. **Replay through current firmware.**
   `make build && tools/replay_log.py <log> --variant <v> --viz --plot`
   - Open-loop: does current firmware send the same ARM_CMD and raise the same DTCs as the field ECU?
     If not, the field unit may run older firmware; note the first divergence.
   - Closed-loop: do the log's conditions (ambient, battery temperature, speed, operator inputs)
     reproduce the fault with the plant model?
   - Note any frame IDs not in the DBC (other ECUs on the bus); they are ignored.
4. **Explain the mechanism from the traces** before changing code: open the plots
   (`out/replay/*.png`) or the viewer (`viz/build.py --traces ...field.trace.json ...resim.trace.json`).
   Read the relevant firmware path (`firmware/src/`) and the variant parameters.
5. **Write the failing test first.** Usually a scenario in `sil/scenarios.py` reproducing the field
   conditions for the affected variant(s), and/or a test that replays the log. Run it and confirm it
   fails on the current code for the reason seen in the field.
6. **Fix** in firmware/parameters. Keep variant differences in YAML; keep thresholds in `params_t`.
   Do not weaken checks or remove variants from scenarios.
7. **Verify:** `ctest`, `make cppcheck`, the full `pytest tests/sil`, and the replay again
   (closed-loop should no longer fault; open-loop will now diverge from the old field ECU, which is
   expected - say so).
8. **PR:** link the ticket; include the DTC decode, the root cause in two sentences, before/after
   plots, the test that failed before the fix, and any follow-ups (field reflash, service bulletin).
