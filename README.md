# Boiler Controller in IEC 61131-3 Structured Text

A hot-water boiler controller written in **IEC 61131-3 Structured Text** (the standard PLC / SPS
language), tested in closed loop against a simulated boiler. The ST program is compiled to C with the
open-source [MATIEC](https://github.com/beremiz/matiec) compiler and driven one PLC scan (100 ms) at a
time from Python, so every behaviour below is covered by an automated test.

![Start-up](docs/startup.svg)

## What the program does

| Function | Implementation |
|---|---|
| Sequence | `OFF -> PUMP_START -> RUN`, any alarm -> `FAULT` (CASE state machine) |
| Temperature control | PI controller with conditional-integration anti-windup, output 0-100 % |
| Flow supervision | Pump must confirm within 5 s of the command; loss of feedback in RUN trips after 3 s |
| High-temperature limit | Trips at 95 degC, **latches**, can only be reset below 85 degC (hysteresis) |
| Sensor plausibility | Open/short circuit (< -10 or > 200 degC) -> alarm, heater off |
| Emergency stop | NC chain, drops pump and heater immediately |
| Setpoint protection | Operator setpoint clamped to 30-90 degC |
| Pump post-circulation | In FAULT the pump keeps running above 60 degC to shed heat (not if the pump is the fault) |

## Results (from the simulation)

| Scenario | Result |
|---|---|
| Start-up 20 -> 80 degC | Overshoot 2.9 K, within +-1 K after ~890 s |
| 5 kW process load step | Setpoint held within 1.5 K, controller output rises |
| Setpoint typed as 150 degC | Clamped to 90 degC, high limit never trips |
| Pump stops while running | `AlmNoFlow` after 3.2 s, heater off |
| Welded heater contactor | High limit trips at 95.0 degC, alarm stays latched until reset |

![High limit](docs/high_limit.svg)

## Run it

```bash
# 1. build MATIEC once (needs gcc, make, bison, flex, autoconf, automake)
git clone https://github.com/beremiz/matiec && cd matiec && autoreconf -i && ./configure && make && cd ..
# 2. compile the ST program to C, build the library and run the 13 tests
make MATIEC=/path/to/matiec test
make MATIEC=/path/to/matiec plots     # regenerates docs/*.svg
```

## Run it in CODESYS (soft PLC)

1. New project -> *Standard project*, device *CODESYS Control Win V3 (soft PLC)*.
2. Add a POU named `BoilerCtrl`, type *Program*, language *ST*.
3. Paste the `VAR_INPUT / VAR_OUTPUT / VAR` blocks from `src/boiler_ctrl.st` into the declaration
   editor and the code between the last `END_VAR` and `END_PROGRAM` into the body.
4. Call it from `PLC_PRG` / a 100 ms task, build, log in, and force the inputs
   (`TempC`, `PumpRunning`, `EStopOK`, `StartCmd`, ...) to step through the sequence.

## Limits (be honest in interviews)

- This is a **control and alarm logic model**, not a safety function. Real boiler safety limiters
  (STB, approved hardware, EN 12952/12953) are independent of the PLC.
- Tested against a simple first-order plant model, not against real hardware.
- Tuning (Kp = 10 %/K, Ki = 0.25 %/(K s)) was chosen for this simulated plant.
