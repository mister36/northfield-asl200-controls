# ASLCTL-163 · ECO · ECO-0412 arm lift position sensor change (software impact)

**Reporter:** Electrical engineering · **Component:** body-controls · **Attachment:** `docs/eco/ECO-0412.md` (`.pdf`)

ECO-0412 replaces the arm lift position sensor (P/N 55-1180-0, EOL) with P/N 55-1180-1 starting
at body serial ASL2-26-04100. The new sensor's output is 0.5–4.5 V instead of 0–5 V ratiometric;
same mechanical mount and angular range. Software must support the new sensor for the
effectivity break. Please update the controller and everything that depends on the sensor range,
and list anything outside the repo that has to change.
