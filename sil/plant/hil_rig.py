"""Hardware-in-the-loop rig adapter (placeholder).

Same interface as SimPlant, so scenarios and checks run unchanged once a
bench is connected: a real ECU on a SocketCAN / PCAN channel, the arm I/O
node and actuator driver either real or emulated by the rig.

Signal -> rig I/O mapping (what a bench needs to provide):

  DBC message / signal               direction   rig I/O
  ---------------------------------  ----------  ------------------------------------------
  CCVS.WheelBasedVehicleSpeed        rig -> ECU  CAN sim node (chassis), 100 ms
  AMB.AmbientAirTemperature          rig -> ECU  CAN sim node (chassis), 1 s
  BATT_STATUS.BatteryTemperature     rig -> ECU  CAN sim node (BMS), 100 ms, electric only
  JOY_CMD.*                          rig -> ECU  operator console (real) or CAN sim node, 50 ms
  BODY_INPUTS.TailgateOpen           rig -> ECU  arm I/O node DI 3 (tailgate prox switch)
  BODY_INPUTS.GripperPressure        rig -> ECU  arm I/O node AI 2 (4-20 mA transducer)
  ARM_SENSORS.LiftSensorVoltage      rig -> ECU  arm I/O node AI 0 <- lift angle sensor / DAC
  ARM_SENSORS.ReachSensorVoltage     rig -> ECU  arm I/O node AI 1 <- reach string pot / DAC
  ACTUATOR_STATUS.LiftActuatorEffort rig -> ECU  actuator driver (pressure or current feedback)
  ARM_CMD.LiftVelocityCmd            ECU -> rig  actuator driver PWM / valve coil, or load motor
  ARM_CMD.ReachVelocityCmd           ECU -> rig  actuator driver PWM / valve coil
  ARM_CMD.GripCmd                    ECU -> rig  gripper valve DO
  ARM_STATE, ARM_POSITION, DM1       ECU -> rig  logged only (assertions read these)

On a rig with a real arm, truth() comes from independent instrumentation
(encoder on the lift pivot) rather than from the ECU's own sensor.
"""
from __future__ import annotations

import can

from .interface import PlantInterface


class HilRigPlant(PlantInterface):
    def __init__(self, channel: str = "can0", interface: str = "socketcan"):
        self.channel = channel
        self.interface = interface

    def attach(self, bus: can.BusABC) -> None:
        raise NotImplementedError("connect bench/HIL rig here")

    def tick(self, t_s: float, dt_s: float) -> list[can.Message]:
        raise NotImplementedError("connect bench/HIL rig here")

    def truth(self) -> dict:
        raise NotImplementedError("connect bench/HIL rig here")
