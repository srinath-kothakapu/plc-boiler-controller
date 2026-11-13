/* Thin C wrapper around the MATIEC-generated code (POUS.c) so the PLC
 * program can be called from Python (ctypes) one scan at a time. */
#include "iec_types_all.h"
#include "accessor.h"
#include "iec_std_lib.h"
#include "POUS.h"
#include "POUS.c"

static BOILERCTRL_data__ plc;

typedef struct {
    float temp_c; int pump_running; int estop_ok;
    int start; int stop; int reset; float setpoint_c;
} plc_in_t;

typedef struct {
    int pump_cmd; int burner_enable; float power_pct; int state;
    int alm_high; int alm_sensor; int alm_noflow; int alm_estop;
} plc_out_t;

void plc_init(void) { BOILERCTRL_init__(&plc, 1); }

void plc_scan(const plc_in_t *in, plc_out_t *out) {
    plc.TEMPC.value = in->temp_c;
    plc.PUMPRUNNING.value = in->pump_running;
    plc.ESTOPOK.value = in->estop_ok;
    plc.STARTCMD.value = in->start;
    plc.STOPCMD.value = in->stop;
    plc.RESETCMD.value = in->reset;
    plc.SETPOINTC.value = in->setpoint_c;
    BOILERCTRL_body__(&plc);
    out->pump_cmd = plc.PUMPCMD.value;
    out->burner_enable = plc.BURNERENABLE.value;
    out->power_pct = plc.POWERPCT.value;
    out->state = plc.STATE.value;
    out->alm_high = plc.ALMHIGHTEMP.value;
    out->alm_sensor = plc.ALMSENSOR.value;
    out->alm_noflow = plc.ALMNOFLOW.value;
    out->alm_estop = plc.ALMESTOP.value;
}
