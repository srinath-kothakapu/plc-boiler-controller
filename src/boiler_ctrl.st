(*==========================================================================
  BoilerCtrl - hot-water boiler controller (IEC 61131-3, Structured Text)

  Learning/portfolio project. Standard-compliant ST: it compiles with the
  open-source MATIEC compiler and can be pasted into a CODESYS PROGRAM POU.

  Functions
    - Start/stop sequence: OFF -> PUMP_START -> RUN -> OFF, FAULT on alarm
    - PI temperature control (anti-windup) with modulated power 0..100 %
    - Pump flow feedback supervision (start timeout, run-time loss)
    - Software high-temperature limit with latching alarm + reset hysteresis
    - Sensor plausibility check (open/short circuit)
    - Emergency-stop input (NC chain: TRUE = healthy)
    - Pump post-circulation (cool-down) in FAULT state

  NOT a safety function: real boiler safety limiters (STB/TUEV-approved
  hardware, EN 12952/12953) are independent of the PLC. This models the
  control and alarm logic only.
==========================================================================*)
PROGRAM BoilerCtrl
  VAR_INPUT
    TempC       : REAL;   (* boiler water temperature [degC]            *)
    PumpRunning : BOOL;   (* feedback: circulation pump is running      *)
    EStopOK     : BOOL;   (* emergency-stop chain, NC: TRUE = healthy   *)
    StartCmd    : BOOL;
    StopCmd     : BOOL;
    ResetCmd    : BOOL;   (* alarm acknowledge, evaluated on rising edge *)
    SetpointC   : REAL;   (* requested water temperature [degC]         *)
  END_VAR
  VAR_OUTPUT
    PumpCmd      : BOOL;
    BurnerEnable : BOOL;
    PowerPct     : REAL;  (* modulated heat output 0..100 %             *)
    State        : INT;   (* 0=OFF 1=PUMP_START 2=RUN 3=FAULT           *)
    AlmHighTemp  : BOOL;
    AlmSensor    : BOOL;
    AlmNoFlow    : BOOL;
    AlmEStop     : BOOL;
  END_VAR
  VAR
    (* tuning and limits *)
    Kp            : REAL := 10.0;   (* % per K                          *)
    Ki            : REAL := 0.25;   (* % per (K*s)                      *)
    CycleS        : REAL := 0.1;    (* scan time [s]                    *)
    SetpointMin   : REAL := 30.0;
    SetpointMax   : REAL := 90.0;
    HighLimit     : REAL := 95.0;   (* trip temperature [degC]          *)
    HighReset     : REAL := 85.0;   (* alarm may be reset below this    *)
    SensorMin     : REAL := -10.0;
    SensorMax     : REAL := 200.0;
    PumpStartTmo  : REAL := 5.0;    (* s to confirm pump after command  *)
    NoFlowTime    : REAL := 3.0;    (* s feedback may be lost in RUN    *)
    CooldownTemp  : REAL := 60.0;   (* pump runs on above this in FAULT *)
    MinPowerPct   : REAL := 1.0;    (* burner enable threshold          *)
    (* internal *)
    Sp            : REAL;
    Err           : REAL;
    IntTerm       : REAL;
    OutUnsat      : REAL;
    SensorBad     : BOOL;
    Fault         : BOOL;
    ResetPrev     : BOOL;
    ResetEdge     : BOOL;
    Cnt           : DINT;           (* scans since state entry/loss     *)
    TimeS         : REAL;
  END_VAR

  (* ---- 1. input conditioning ---------------------------------------- *)
  SensorBad := (TempC < SensorMin) OR (TempC > SensorMax);

  IF SetpointC < SetpointMin THEN
    Sp := SetpointMin;
  ELSIF SetpointC > SetpointMax THEN
    Sp := SetpointMax;
  ELSE
    Sp := SetpointC;
  END_IF;

  ResetEdge := ResetCmd AND NOT ResetPrev;
  ResetPrev := ResetCmd;

  (* ---- 2. latching alarms ------------------------------------------- *)
  IF SensorBad THEN AlmSensor := TRUE; END_IF;
  IF (NOT SensorBad) AND (TempC >= HighLimit) THEN AlmHighTemp := TRUE; END_IF;
  IF NOT EStopOK THEN AlmEStop := TRUE; END_IF;

  IF ResetEdge THEN
    IF NOT SensorBad THEN AlmSensor := FALSE; END_IF;
    IF (NOT SensorBad) AND (TempC < HighReset) THEN AlmHighTemp := FALSE; END_IF;
    IF EStopOK THEN AlmEStop := FALSE; END_IF;
    AlmNoFlow := FALSE;   (* cause is re-checked on the next start *)
  END_IF;

  (* ---- 3. sequence -------------------------------------------------- *)
  CASE State OF
    0: (* OFF *)
      IF StartCmd THEN
        State := 1;
        Cnt   := 0;
      END_IF;

    1: (* PUMP_START: wait for pump feedback *)
      Cnt := Cnt + 1;
      TimeS := DINT_TO_REAL(Cnt) * CycleS;
      IF PumpRunning THEN
        State   := 2;
        Cnt     := 0;
        IntTerm := 0.0;
      ELSIF TimeS > PumpStartTmo THEN
        AlmNoFlow := TRUE;
      END_IF;
      IF StopCmd THEN State := 0; END_IF;

    2: (* RUN: supervise flow, control temperature *)
      IF PumpRunning THEN
        Cnt := 0;
      ELSE
        Cnt := Cnt + 1;
        TimeS := DINT_TO_REAL(Cnt) * CycleS;
        IF TimeS > NoFlowTime THEN AlmNoFlow := TRUE; END_IF;
      END_IF;
      IF StopCmd THEN State := 0; END_IF;

    3: (* FAULT: leaves only when all alarms are acknowledged *)
      Cnt := 0;
  END_CASE;

  Fault := AlmHighTemp OR AlmSensor OR AlmNoFlow OR AlmEStop;
  IF Fault THEN
    State := 3;
  ELSIF State = 3 THEN
    State := 0;
  END_IF;

  (* ---- 4. PI controller (only in RUN) ------------------------------- *)
  IF State = 2 THEN
    Err      := Sp - TempC;
    OutUnsat := Kp * Err + IntTerm;
    (* conditional integration = anti-windup *)
    IF NOT (((OutUnsat >= 100.0) AND (Err > 0.0)) OR ((OutUnsat <= 0.0) AND (Err < 0.0))) THEN
      IntTerm := IntTerm + Ki * Err * CycleS;
    END_IF;
    IF IntTerm > 100.0 THEN IntTerm := 100.0; END_IF;
    IF IntTerm < 0.0   THEN IntTerm := 0.0;   END_IF;
    OutUnsat := Kp * Err + IntTerm;
    IF OutUnsat > 100.0 THEN
      PowerPct := 100.0;
    ELSIF OutUnsat < 0.0 THEN
      PowerPct := 0.0;
    ELSE
      PowerPct := OutUnsat;
    END_IF;
  ELSE
    IntTerm  := 0.0;
    PowerPct := 0.0;
  END_IF;

  (* ---- 5. outputs --------------------------------------------------- *)
  BurnerEnable := (State = 2) AND (PowerPct > MinPowerPct);

  IF AlmEStop THEN
    PumpCmd := FALSE;                          (* e-stop: all outputs off *)
  ELSIF State = 1 OR State = 2 THEN
    PumpCmd := TRUE;
  ELSIF State = 3 THEN
    (* post-circulation to dissipate heat, unless pump itself is the fault *)
    PumpCmd := (SensorBad OR (TempC > CooldownTemp)) AND (NOT AlmNoFlow);
  ELSE
    PumpCmd := FALSE;
  END_IF;

END_PROGRAM
