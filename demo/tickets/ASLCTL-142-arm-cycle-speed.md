# ASLCTL-142 · Story · Increase arm cycle speed ~15% across ASL-200 line

**Reporter:** Product management · **Component:** body-controls · **Priority:** High
**Labels:** cycle-time, customer-request

Increase arm cycle speed ~15% across the ASL-200 line to hit the customer cycle-time target
(≤ 9.0 s per lift). Must not change interlock behaviour.

Two municipal fleets have benchmarked our auto-cycle at ~10.3 s per lift (reach-out to arm home)
against a competitor at ~9 s. Route planning assumes ~1,100 lifts/shift, so 15% is roughly
45 minutes per truck per shift.

## Acceptance criteria

- [ ] Auto-cycle time (REACH_OUT → back in IDLE) reduced by ≥ 12% on every ASL-200 variant in the
      SIL `normal` scenario.
- [ ] No change to interlock behaviour: vehicle speed, tailgate, battery temperature, grip-secured.
- [ ] Arm never exceeds a variant's soft limits, in any scenario.
- [ ] No new DTCs in any scenario.
- [ ] CI SIL matrix green for all variants.
