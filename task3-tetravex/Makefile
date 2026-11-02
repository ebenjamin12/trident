# Convenience targets. Everything here is a thin wrapper around the CLI.
PY ?= python3

.PHONY: help engines test bench demo clean

help:
	@echo "make engines  - report which solver backends are usable"
	@echo "make test     - run the pytest suite"
	@echo "make bench    - run the benchmark (writes bench/)"
	@echo "make demo     - generate, solve with both engines, verify and render"
	@echo "make clean    - remove caches and generated demo files"

engines:
	$(PY) -m tetravex engines

test:
	$(PY) -m pytest tests/ -q

bench:
	$(PY) -m tetravex.bench --sizes 2x2,2x3,3x3,3x4,4x4 --seeds 1,2,3 --reps 3

demo:
	$(PY) -m tetravex generate --rows 3 --cols 3 --symbols 10 --seed 42 -o /tmp/tv.json
	$(PY) -m tetravex solve /tmp/tv.json --engine z3     --unique -o /tmp/tv-z3.json
	$(PY) -m tetravex solve /tmp/tv.json --engine prolog --unique -o /tmp/tv-pl.json
	$(PY) -m tetravex verify /tmp/tv.json /tmp/tv-z3.json
	$(PY) -m tetravex verify /tmp/tv.json /tmp/tv-pl.json
	$(PY) -m tetravex render /tmp/tv.json --solution /tmp/tv-z3.json --ids

clean:
	rm -rf __pycache__ */__pycache__ */*/__pycache__ .pytest_cache /tmp/tv*.json
