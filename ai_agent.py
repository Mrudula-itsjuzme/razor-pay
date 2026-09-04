from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Any, List
import networkx as nx

class BaseInvestigator(ABC):
    @abstractmethod
    def analyze(self, subgraph: nx.DiGraph, expected_amount: Decimal, observed_amount: Decimal) -> Dict[str, Any]:
        pass

class OfflineFallbackInvestigator(BaseInvestigator):
    """
    Deterministic/offline investigator used when LLM credentials are absent.
    """
    def analyze(self, subgraph: nx.DiGraph, expected_amount: Decimal, observed_amount: Decimal) -> Dict[str, Any]:
        diff = expected_amount - observed_amount
        
        refunds = [data['data'] for node, data in subgraph.nodes(data=True) if data.get('type') == 'Refund']
        fees = [data['data'] for node, data in subgraph.nodes(data=True) if data.get('type') == 'Fee']
        taxes = [data['data'] for node, data in subgraph.nodes(data=True) if data.get('type') == 'Tax']
        
        supported_hypotheses = []
        unsupported_hypotheses = []
        confidence = 0.0
        resolution = "UNRESOLVED"
        broken_edge = "UNKNOWN"
        
        # 1. Check if it's a temporal exception with no amount difference
        if diff == Decimal('0.00'):
            supported_hypotheses.append("SLA breached for Bank Transaction. Downstream evidence missing.")
            confidence = 0.99
            resolution = "EXCEPTION_MISSING_BANK_TX"
            broken_edge = "Settlement -> BankTransaction"
        
        # 2. Missing refund
        elif resolution == "UNRESOLVED":
            unsupported_hypotheses.append(f"Missing refund of {diff}")
            for r in refunds:
                if r.amount == diff:
                    supported_hypotheses.append(f"Post-capture partial refund of {diff} exists but unlinked")
                    unsupported_hypotheses.pop()
                    confidence = 0.98
                    resolution = "RECONCILED_WITH_PARTIAL_REFUND"
                    broken_edge = "Payment -> Refund -> Settlement"
                    break
                    
        # 3. Missing fee (Standard 2% rate)
        if resolution == "UNRESOLVED":
            order_amount = next((data['data'].amount for n, data in subgraph.nodes(data=True) if data.get('type') == 'Order'), expected_amount)
            fee_estimate = (order_amount * Decimal('0.02')).quantize(Decimal('0.01'))
            tax_estimate = (fee_estimate * Decimal('0.18')).quantize(Decimal('0.01'))
            
            if abs(diff - fee_estimate) <= Decimal('0.5') or abs(diff - (fee_estimate + tax_estimate)) <= Decimal('0.5'):
                unsupported_hypotheses.append(f"Difference exactly matches standard 2% fee deduction, but NO actual fee record exists in system.")
                # We intentionally DO NOT set resolution to RECONCILED. It must remain UNRESOLVED because hypothesis != evidence.
                broken_edge = "Payment -> Fee (Missing Node)"
            else:
                unsupported_hypotheses.append(f"Missing fee of {diff}")
                
            for f in fees:
                if f.amount == diff:
                    supported_hypotheses.append(f"Fee deduction of {diff} exists")
                    if f"Missing fee of {diff}" in unsupported_hypotheses:
                        unsupported_hypotheses.remove(f"Missing fee of {diff}")
                    confidence = 0.95
                    resolution = "RECONCILED_WITH_FEE"
                    broken_edge = "Payment -> Fee -> Settlement"
                    break
                    
        if resolution == "UNRESOLVED":
            confidence = 0.1
            resolution = "HUMAN_REVIEW_REQUIRED"
            
        return {
            "broken_edge": broken_edge,
            "observed_facts": [f"Expected: {expected_amount}", f"Observed: {observed_amount}"],
            "derived_facts": [f"Difference: {diff}"],
            "hypotheses": supported_hypotheses + unsupported_hypotheses,
            "supported_hypotheses": supported_hypotheses,
            "unsupported_hypotheses": unsupported_hypotheses,
            "confidence": str(confidence),
            "recommended_action": resolution,
            "requires_human_review": resolution == "HUMAN_REVIEW_REQUIRED",
            "provider": "OfflineFallbackInvestigator",
            # Legacy compatibility for UI
            "expected": str(expected_amount),
            "observed": str(observed_amount),
            "difference": str(diff),
            "likely_causes": supported_hypotheses,
            "counterfactuals_tested": unsupported_hypotheses + supported_hypotheses
        }

class LLMInvestigator(BaseInvestigator):
    """
    Real LLM Investigator. Never creates evidence.
    """
    def analyze(self, subgraph: nx.DiGraph, expected_amount: Decimal, observed_amount: Decimal) -> Dict[str, Any]:
        # Implementation left for when credentials are provided
        pass

def analyze_exception(subgraph: nx.DiGraph, expected_amount: Decimal, observed_amount: Decimal) -> Dict[str, Any]:
    # Use offline fallback
    investigator = OfflineFallbackInvestigator()
    return investigator.analyze(subgraph, expected_amount, observed_amount)

