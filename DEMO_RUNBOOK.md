# ASL-200 demo runbook

Audience: controls / electrical engineering leadership. Their stated pain: *testing, not coding, is
the bottleneck.* Every segment starts from a real artifact (question, ticket, field log, ECO),
and ends with CI evidence (variant × scenario matrix, plots, animated viewer).

**Order:** if the call is about field testing / quality, run **C first, then B**. A and D are
optional pivots (A for "can it understand our code?", D for "what about change orders?").

## Before the call (10 min)

```bash
scripts/reset_demo.sh --apply        # closes demo-live PRs, recreates demo/segment-* from demo-start
make sil && make viz                 # local sanity check: all green, cold-electric not in the matrix
```

- Open the backup PRs (links in the table below) in browser tabs, scrolled to the CI comment.
- Open the side-by-side viewers from the backup PRs' `sil-report` artifacts (download, unzip,
  open `matrix.html`, click the failing cell) - or locally:
  `python3 viz/build.py --traces <before>.trace.json <after>.trace.json --html /tmp/compare.html`.
- Have the GitHub Issues (or Jira `ASLCTL`) tickets open: ASLCTL-142, ASLCTL-157, ASLCTL-163.

| Segment | Ticket | Live input | Backup PR | Run time |
|---|---|---|---|---|
| A | - | Slack / Ask Devin question | (answers verified, below) | 2–3 min |
| B | ASLCTL-142 | ticket text | [#8](https://github.com/mister36/northfield-asl200-controls/pull/8) | 12–20 min |
| C | ASLCTL-157 | ticket text + `field_logs/unit4471_2026-01-14_0642.log` | [#6](https://github.com/mister36/northfield-asl200-controls/pull/6) | 15–25 min |
| D | ASLCTL-163 | ticket text + `docs/eco/ECO-0412.pdf` | [#5](https://github.com/mister36/northfield-asl200-controls/pull/5) | 10–15 min |

What each backup PR did (all labelled `demo-backup`, CI green, left open - do not merge):

- **B, [#8](https://github.com/mister36/northfield-asl200-controls/pull/8):** the +15% change on shared speeds breaks only electric: the lift overshoots to ~160-162 deg
  against a 155 deg soft limit, because regen braking limits how fast it can slow down. Fixed with electric-only
  motion overrides that stay within that braking limit. Cycle time −12.9% to −14.1% on all four variants; no
  interlock, check or scenario changes.
- **C, [#6](https://github.com/mister36/northfield-asl200-controls/pull/6):** failing regression committed first, then the fix: before the arm first moves, the stall
  timer gets extra time scaled by pack temperature (electric: up to +700 ms; others: 0). After first motion the
  timer is back to 400 ms, and the new `cold_lift_jam` scenario shows a real jam still trips. `cold` now runs on
  the electric variant too.
- **D, [#5](https://github.com/mister36/northfield-asl200-controls/pull/5):** separate `*_eco0412` firmware variants (0.5-4.5 V lift calibration) for ASL2-26-04100 onward
  and retrofits; open/short thresholds kept at 0.25/4.75 V; DBC, I/O map, release notes, short-to-supply
  scenario and a non-code follow-ups checklist in the PR body.

Live runs take longer than the call allows: start the live session, narrate the first minutes
(reading code, running the replay), then switch to the backup PR for the result.

---

## Segment C - field bug → fix (lead with this)

**Input** (paste into Devin, or assign the ticket / post in `#asl-controls` with the log attached):

> ASLCTL-157: Unit 4471 (ASL-200 electric, Mack LR). Route 12, approx 6:42am, ambient about −5°F.
> Arm stalled partway up on first few lifts, threw arm fault, driver had to reset. Worked fine
> after ~20 min. Log pulled from gateway, attached. […] Please triage using the field log and
> open a PR with the fix.

**Expected Devin behaviour**

1. Picks up the `triage-field-log` skill. `tools/decode_dtc.py --log` → three
   `SPN 520210 FMI 7 Arm lift not responding` events ~18 s, 45 s, 76 s, each after a reset.
2. `tools/replay_log.py ... --variant asl200_electric_mack --viz --plot`: open-loop replay
   matches the field ECU frame-for-frame and reproduces all three DTCs; closed-loop re-sim at the
   logged −20.6 °C ambient / −18.4 °C battery reproduces the stall. Notes 3 non-ASL frame IDs ignored.
3. Explains the mechanism from the trace (lift commanded, actual flat, fault fires) and why CI
   never caught it.
4. Writes the failing regression test first, then fixes, then shows the matrix green and the
   closed-loop replay clean. (Expected root cause and fix: see `RUNBOOK_ANSWERS.md` on the
   internal `demo-assets` branch - kept off `main` so the live session has to find it.)

**What to show:** the decode output; the replay verdict; the side-by-side viewer (left: field log,
arm freezes ~24° with DM1 red; right: fixed SIL completes the cycle); the PR diff (test first,
then fix); the CI matrix comment with the new cold/electric cell.

**Talking points**
- "Your tech's note plus a gateway log is enough to reproduce a field fault on a laptop in seconds."
- "The test that would have caught it is now in the matrix for every future change."
- "Replay is literally the logged CAN frames on a bus - the same harness works against your rig."
- Open-loop vs closed-loop: one proves the firmware in the field is the firmware in the repo; the
  other proves the fix under the field conditions.

**Open the viewer when:** Devin reports the reproduction (before the fix) and again at the end
with before/after.

## Segment B - test before the field

**Input:** ASLCTL-142 (`demo/tickets/ASLCTL-142-arm-cycle-speed.md`).

**Expected Devin behaviour:** finds the motion parameters in `variants/common.yaml`, makes the
naive change (+15% lift/lower/reach speed), runs the matrix: diesel, CNG and long-reach pass;
`asl200_electric_mack` fails `soft_limits` (lift peaks ~160–162° vs 155° soft limit) in normal,
hot, arm-at-limit and vehicle-moving. Devin works out why only that variant fails and scopes the
change accordingly, without touching interlocks or weakening tests. Matrix green; cycle-time
reduction reported per variant. (Expected fix: `RUNBOOK_ANSWERS.md` on `demo-assets`.)

**What to show:** the failing CI matrix (one red row), the viewer on electric/normal (arm turns red
past the soft limit, overshoot marker on the arc), then the fixed PR's green matrix.

**Talking points:** "This is the bug that a single-variant bench test misses and a customer finds.
The variant × scenario matrix ran in under a minute, on every push." / "Devin didn't weaken the test;
it fixed the cause."

**Open the viewer when:** the matrix comes back red - click the electric/normal cell.

## Segment A - understand the code (optional)

Verified answers:

1. *Where is the vehicle-speed interlock enforced, and which variants override its threshold?*
   `interlock_vehicle_speed()` in `firmware/src/interlocks.c`, called from `controller_step()` in
   `firmware/src/controller.c`; it uses `p->interlocks.vehicle_speed_limit_mph` (3.0 mph in
   `variants/common.yaml`) and a CCVS timeout. Only `asl200_diesel_mack_longreach` overrides it
   (2.0 mph).
2. *What CAN messages does the body send, and who consumes each one?* ARM_CMD (actuator driver,
   10 ms), ARM_STATE and ARM_POSITION (cab display / telematics), DM1 (display, service tool,
   telematics) - `firmware/src/can_io.c`, `can/asl200.dbc`, `docs/io-map.md`.
3. *If I change the arm position sensor, what code and docs are affected?* `controls.sensors.lift`
   in `variants/common.yaml` (+ `hardware.sensors.lift` for the plant), `scale_lift_mv_to_deg()` /
   `sensor_check_mv()` in `firmware/src/scaling.c`, `update_sensors()` in `controller.c`, DBC
   comment on `ARM_SENSORS.LiftSensorVoltage`, `docs/io-map.md`, `docs/faults.md`,
   `tests/unit/test_scaling.c`, the sensor-dropout scenario.

## Segment D - change-order ripple (optional)

**Input:** ASLCTL-163 + `docs/eco/ECO-0412.pdf`.

**Expected:** one PR updating sensor calibration and open/short thresholds in the variant YAML,
plant sensor model, DBC comment and range, unit tests for the new thresholds, `io-map.md`
(including correcting the stale threshold row), `faults.md`; matrix green; PR body has a
non-code checklist: BOM / ECO sign-off, service manual, technical service bulletin for mixed
fleets, end-of-line test spec, service tool limits.

**Talking point:** "An ECO is a ripple, not a one-liner. Devin carries it through code, CAN
database, tests and docs, and hands your team the list of what it cannot change."

---

## 60-second SIL / HIL talk track

Open `sil/plant/interface.py` and `sil/plant/hil_rig.py`.

> "The controller is plain C - the same source cross-compiles for the ECU in CI. In SIL we compile
> it as a library and put it on a virtual CAN bus. Everything it sees and sends is real J1939
> frames from your DBC; it can't tell a simulated plant from a log replay. The plant is a
> `PlantInterface`: `SimPlant` models the arm, hydraulics or electric actuator, temperature and
> sensors. `HilRigPlant` has the same interface - this stub is where your bench plugs in: a
> SocketCAN channel to the rig, and the same scenarios and checks run against hardware. So the
> matrix Devin runs on every PR is the same matrix your rig runs overnight."

## If something goes wrong

- CI slow or down: use the backup PR's existing comment and artifact.
- Live session wanders: switch to the backup PR, say "here's the run from this morning".
- Viewer won't load a trace from `file://` with `?trace=`: use "Open trace(s)" or drag the files in.
