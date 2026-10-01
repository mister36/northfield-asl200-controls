# ASL-200 body controls - developer entry points.
PY        ?= python3
BUILD     ?= build
OUT       ?= out
VARIANT   ?=
JOBS      ?= $(shell nproc 2>/dev/null || echo 4)
VARIANT_ARGS = $(if $(VARIANT),--variant $(VARIANT),)

.PHONY: all build unit cppcheck sil sil-fast viz replay ci clean params validate

all: build unit sil

build:
	cmake -S . -B $(BUILD) -DCMAKE_BUILD_TYPE=Release
	cmake --build $(BUILD) -j$(JOBS)

params validate:
	$(PY) codegen/gen_params.py --out $(BUILD)/generated

unit: build
	ctest --test-dir $(BUILD) --output-on-failure

cppcheck: build
	cppcheck --enable=warning,style,performance,portability --std=c99 --inline-suppr --error-exitcode=1 \
	  -I firmware/include -I $(BUILD)/generated -DPARAMS_HEADER='"params_asl200_diesel_autocar.h"' \
	  --suppress=missingIncludeSystem --quiet firmware/

## Full variant x scenario matrix (traces, plots, results under out/)
sil: build
	$(PY) -m pytest tests/sil $(VARIANT_ARGS) -q
	$(PY) -m sil.matrix --out $(OUT) --summary-only

viz: sil
	$(PY) viz/build.py --out $(OUT)
	@echo "open $(OUT)/matrix.html"

## make replay LOG=field_logs/unit4471_2026-01-14_0642.log VARIANT=asl200_electric_mack
replay: build
	$(PY) tools/replay_log.py $(LOG) --variant $(VARIANT) --viz --plot

ci: build unit cppcheck sil viz

clean:
	rm -rf $(BUILD) $(OUT)
