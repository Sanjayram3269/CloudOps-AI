.PHONY: install test api web compose down

install:
	python -m pip install -r requirements.txt

test:
	pytest

api:
	uvicorn backend.app.main:app --reload --port 8000

web:
	cd frontend && npm install && npm run dev

compose:
	docker compose up --build

down:
	docker compose down
