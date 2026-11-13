# Build the ST program into a shared library and run the simulation tests.
# Needs the open-source MATIEC compiler: https://github.com/beremiz/matiec
#   make MATIEC=/path/to/matiec        (directory containing iec2c and lib/)
MATIEC ?= ../build/matiec
BUILD  := build

all: $(BUILD)/libplc.so

$(BUILD)/POUS.c: src/boiler_ctrl.st
	mkdir -p $(BUILD)
	$(MATIEC)/iec2c -I $(MATIEC)/lib -T $(BUILD) src/boiler_ctrl.st

$(BUILD)/libplc.so: $(BUILD)/POUS.c sim/plc_wrapper.c
	gcc -shared -fPIC -O2 -Wall -Wno-unused-function -I$(BUILD) -I$(MATIEC)/lib/C -o $@ sim/plc_wrapper.c

test: all
	python3 -m pytest -q tests

plots: all
	python3 sim/make_plots.py

clean:
	rm -rf $(BUILD)
