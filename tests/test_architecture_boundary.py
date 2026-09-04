import ast
import os

def test_reconciliation_module_has_no_vendor_model_imports():
    """
    Architectural Boundary Test:
    Ensures that reconciliation.py does not import model-provider vendor libraries
    (e.g., openai, anthropic, google.generativeai, langchain, openrouter, etc.).
    """
    filepath = os.path.join(os.path.dirname(__file__), "..", "reconciliation.py")
    with open(filepath, "r") as f:
        tree = ast.parse(f.read(), filename=filepath)

    forbidden_packages = {
        "openai", "anthropic", "google.generativeai", "langchain",
        "openrouter", "transformers", "cohere", "ollama"
    }

    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module.split('.')[0])

    forbidden_found = imported_modules.intersection(forbidden_packages)
    assert not forbidden_found, f"reconciliation.py imports forbidden AI vendor packages: {forbidden_found}"

def test_deterministic_closure_gate_purity():
    """
    Ensures that authorize_closure method in ReconciliationEngine strictly computes
    closure authority as a pure boolean evaluation of explicit validation gates.
    """
    from reconciliation import ReconciliationEngine
    engine = ReconciliationEngine()

    # All gates True -> closure authorized
    assert engine.authorize_closure(
        accounting_valid=True,
        evidence_contract_valid=True,
        provenance_valid=True,
        temporal_valid=True,
        contradiction_valid=True,
        currency_valid=True,
        proof_complete=True
    ) is True

    # Any single gate False -> closure forbidden
    assert engine.authorize_closure(
        accounting_valid=True,
        evidence_contract_valid=True,
        provenance_valid=True,
        temporal_valid=False, # Invalid temporal state
        contradiction_valid=True,
        currency_valid=True,
        proof_complete=True
    ) is False
