PYTHON ?= python3.12
.PHONY: setup train test up down smoke demo export validate
setup:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -r requirements.txt
train:
	$(PYTHON) -m ml.generate
	$(PYTHON) -m ml.train
	$(PYTHON) -m ml.evaluate
test:
	$(PYTHON) -m pytest -q
up:
	docker compose up --build -d
smoke:
	$(PYTHON) -m scripts.smoke
demo:
	$(PYTHON) -m scripts.demo_report
export:
	$(PYTHON) -m scripts.export_metrics
validate:
	docker compose config --quiet
	docker compose run --rm --no-deps --entrypoint promtool prometheus check config /etc/prometheus/prometheus.yml
	docker compose run --rm --no-deps --entrypoint promtool prometheus test rules /etc/prometheus/test_rules.yml
down:
	docker compose down
