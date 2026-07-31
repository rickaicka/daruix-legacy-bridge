.PHONY: install test run docker-build
install:
	python -m pip install -e ".[dev]"
test:
	pytest --cov=app --cov-report=term-missing
run:
	uvicorn app.main:app --host 127.0.0.1 --port 8100 --reload
docker-build:
	docker compose build

