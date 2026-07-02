# Text-to-Layout developer entry points.
#
# The three-command simulator flow for a fresh clone:
#
#     make setup-simulators    # install/detect JoSIM; detect PSCAN2/WRspice
#     make check-simulators    # availability table (honest, exit 0 when optional sims absent)
#     make demo-jpa            # JPA prompt -> layout -> verification -> simulation prep/run
#
# On Windows without `make`, run the underlying commands directly:
#     python scripts/bootstrap_simulators.py
#     python scripts/check_simulators.py
#     uv run --no-sync textlayout prompt "..." --out out/jpa_demo

PYTHON ?= python
RUN ?= uv run --no-sync

JPA_PROMPT = Design a lumped-element JPA for 2.3 GHz with 50 MHz bandwidth, 13 dB gain target, using an IDC capacitor and SQUID-equivalent inductance. Generate layout, verify it, extract capacitance if possible, and prepare JoSIM, PSCAN2, and WRspice simulations.

.PHONY: setup-simulators check-simulators demo-jpa demo-jpa-strict docker-simulators test lint

setup-simulators:
	$(PYTHON) scripts/bootstrap_simulators.py

check-simulators:
	$(PYTHON) scripts/check_simulators.py

demo-jpa:
	$(RUN) textlayout prompt "$(JPA_PROMPT)" --out out/jpa_demo

demo-jpa-strict:
	$(RUN) textlayout prompt "$(JPA_PROMPT)" --out out/jpa_demo_strict --strict-simulation

docker-simulators:
	docker build -f docker/simulators.Dockerfile -t textlayout-simulators .

test:
	$(RUN) pytest -q

lint:
	$(RUN) ruff check .
	$(RUN) ruff format --check .
	$(RUN) mypy src/textlayout
