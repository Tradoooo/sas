# Sas — developer commands. CI runs the same targets (5-minute budget).

PYTHON ?= python3
PYTEST ?= $(PYTHON) -m pytest
RUFF   ?= $(PYTHON) -m ruff
SRC    := src tests demo eval infra scripts

.PHONY: help install lint format limits test smoke demo attest contest all clean

help:
	@echo "make install  - dev dependencies (offline, stdlib first)"
	@echo "make lint     - ruff check + format --check"
	@echo "make format   - ruff format (writes)"
	@echo "make limits   - < 500 lines per file, < 50 per function"
	@echo "make test     - offline unit + integration tests"
	@echo "make smoke    - one shadow campaign on 2 scenarios, full journal"
	@echo "make demo     - the 3-minute demo: 3 guest agents, 3 verdicts"
	@echo "make attest   - print the attestation of the last campaign"
	@echo "make contest  - hackathon submission conformity check"
	@echo "make all      - lint + limits + test (what CI runs)"

install:
	$(PYTHON) -m pip install --user -e ".[dev,api]"

lint:
	$(RUFF) check $(SRC)
	$(RUFF) format --check $(SRC)

format:
	$(RUFF) format $(SRC)
	$(RUFF) check --fix $(SRC)

limits:
	$(PYTHON) scripts/check_limits.py

test:
	PYTHONPATH=src $(PYTEST) -m "not slow and not aws"

smoke:
	PYTHONPATH=src $(PYTHON) -m sas.cli smoke

demo:
	PYTHONPATH=src $(PYTHON) -m sas.cli demo

attest:
	PYTHONPATH=src $(PYTHON) -m sas.cli attestation --derniere

contest:
	$(PYTHON) scripts/check_contest.py

all: lint limits test

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info data/generated .var
