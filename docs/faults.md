# Diagnostic trouble codes

Reported in DM1 (PGN 65226) from source address 0x21. SPNs 520192–524287 are the J1939
proprietary range. Lookup table used by the tools: `can/faults.yaml`
(`tools/decode_dtc.py --list`).

| SPN | FMI | Name | Condition | Reaction |
|---|---|---|---|---|
| 520200 | 4 | Lift position sensor low | Lift sensor below open-circuit threshold for `debounce_ms` | FAULT_STOP |
| 520200 | 3 | Lift position sensor high | Lift sensor above short threshold for `debounce_ms` | FAULT_STOP |
| 520201 | 4 / 3 | Reach position sensor low / high | As above, reach sensor | FAULT_STOP |
| 520210 | 7 | Arm lift not responding | Lift commanded, first travel < `stall_min_travel_deg` within `stall_onset_ms`, or a motionless gap lasting `stall_timeout_ms` once moving | FAULT_STOP |
| 520211 | 7 | Arm reach not responding | Reach commanded, first travel < `stall_min_travel_mm` within `stall_onset_ms`, or a motionless gap lasting `stall_timeout_ms` once moving | FAULT_STOP |

SPN 520220 (gripper) and 520240 (lift travel) are allocated in `can/faults.yaml` for the service
tool but not raised by the current firmware: a grip that does not secure within `grip_timeout_ms`
aborts the cycle (release + retract) without a DTC.

Faults latch until the operator presses fault reset (accepted once the position sensors read valid). Active DTCs set the
red stop and amber warning lamps in DM1.
