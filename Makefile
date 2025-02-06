.PHONY: help install run import clean

help:
	@echo "Available commands:"
	@echo "  make install    Install dependencies"
	@echo "  make run       Start data collector"
	@echo "  make import    Import historical data"
	@echo "  make clean     Clean up temporary files"

install:
	pip install -r requirements.txt

run:
	docker-compose --profile collector up -d collector

import:
	docker-compose --profile importer up importer

clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -r {} +
	find . -type d -name ".mypy_cache" -exec rm -r {} + 