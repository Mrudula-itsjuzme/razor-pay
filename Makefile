.PHONY: demo test eval eval-scale

demo:
	@echo "Starting local application..."
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -q

eval:
	PYTHONPATH=. python3 evaluation/run_v2_1.py

eval-scale:
	PYTHONPATH=. python3 evaluation/run_scale.py
