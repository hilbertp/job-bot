.PHONY: help test check-secrets dashboard

help:
	@echo "make test           run pytest"
	@echo "make check-secrets  fail if personal data is tracked by git"
	@echo "make dashboard      start the local dashboard on http://localhost:5001"

test:
	python -m pytest -q

check-secrets:
	./scripts/check-secrets.sh

dashboard:
	jobbot dashboard
