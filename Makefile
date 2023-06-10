# This Makefile supports incremental builds, please don't break that if you make any changes.

# user-facing targets

.PHONY: index

all: clone index

clone: cleancache cache

index: cache
	.venv/bin/python indexer.py repositories.yaml

clean: cleancache
	-rm -rf clonerepos.sh .venv

cleancache:
	-rm -rf cache

# other targets

clonerepos.sh: .venv repositories.yaml
	.venv/bin/python parser.py repositories.yaml clonerepos.sh

cache: clonerepos.sh
	-rm -rf cache
	./clonerepos.sh

.venv:
	python3 -m venv .venv
	.venv/bin/pip install pyyaml
