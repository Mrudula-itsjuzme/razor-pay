.PHONY: test test-no-ai eval eval-scale demo verify

test:
	PYTHONPATH=. pytest -q

test-no-ai:
	PYTHONPATH=. pytest -q tests/test_no_ai.py

eval:
	PYTHONPATH=. python3 evaluation/run_v2_1.py

eval-scale:
	PYTHONPATH=. python3 evaluation/run_scale.py

demo:
	uvicorn main:app --host 127.0.0.1 --port 8000

verify: test test-no-ai eval eval-scale
