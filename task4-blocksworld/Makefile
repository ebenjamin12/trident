# Convenience targets. Everything here is a thin wrapper around the CLI.
PY ?= python3

.PHONY: help engines test bench demo clean

help:
	@echo "make engines  - report which planning engines are usable"
	@echo "make test     - run the pytest suite"
	@echo "make bench    - run the block-count scaling benchmark"
	@echo "make demo     - generate, plan with both engines, verify, animate"
	@echo "make clean    - remove caches and generated demo files"

engines:
	$(PY) -m blocksworld engines

test:
	$(PY) -m pytest tests/ -q

bench:
	$(PY) -m blocksworld.bench --suites blocks --blocks 3,4,5,6,7,8 \
		--seeds 1,2,3 --reps 3 --max-stacks 2

demo:
	$(PY) -m blocksworld generate --blocks 6 --seed 1 --max-stacks 2 -o /tmp/bw.json
	$(PY) -m blocksworld solve /tmp/bw.json --engine prolog -o /tmp/bw-pl.json --explain
	$(PY) -m blocksworld solve /tmp/bw.json --engine z3     -o /tmp/bw-z3.json
	$(PY) -m blocksworld verify /tmp/bw.json /tmp/bw-pl.json
	$(PY) -m blocksworld verify /tmp/bw.json /tmp/bw-z3.json
	$(PY) -m blocksworld render /tmp/bw.json --solution /tmp/bw-pl.json --format gif -o /tmp/bw.gif

clean:
	rm -rf __pycache__ */__pycache__ */*/__pycache__ .pytest_cache /tmp/bw*.json /tmp/bw.gif
