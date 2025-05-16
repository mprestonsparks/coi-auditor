# Makefile for coi-auditor project

.PHONY: test lint clean-logs run dump-log

test:
	python -m unittest discover -s coi_auditor/tests

lint:
	pyright coi_auditor/src

clean-logs:
	rm -f logs/*.log logs/*.txt

run:
	python -m coi_auditor.src.main

dump-log:
	python -m coi_auditor.src.dump_log
