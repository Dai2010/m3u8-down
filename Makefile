PYTHON=python3

all: test

test:
	$(PYTHON) -m pytest tests

python-test:
	$(PYTHON) -m pytest tests

fmt:
	$(PYTHON) -m compileall m3u8_downloader tests

run:
	$(PYTHON) -m m3u8_downloader.main

clean:
	rm -rf .pytest_cache build dist *.egg-info

.PHONY: all test python-test fmt run clean
