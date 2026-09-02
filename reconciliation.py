from datetime import datetime, timedelta
import networkx as nx
from decimal import Decimal
from typing import Dict, Any, List, Optional
from ai_agent import analyze_exception
from models import SettlementItem

class ReconciliationEngine:
    def __init__(self, tolerance: Decimal = Decimal('0.00'), settlement_window_days: int = 3, evaluation_time: Optional[datetime] = None):
        self.tolerance = tolerance
        self.settlement_window_days = settlement_window_days
        # Use a fixed evaluation time slightly after the datagen window if none provided
        self.evaluation_time = evaluation_time or datetime(2026, 8, 15)

    def reconcile_order(self, graph: nx.DiGraph, max_layer: int = 4) -> Dict[str, Any]:
        """
        Takes an order subgraph and attempts to reconcile it across the layers.
        Returns the audit trail.
        """
        nodes_by_type = {}
        for n, data in graph.nodes(data=True):
            t = data.get('type')
            if t and 'data' in data:
                nodes_by_type.setdefault(t, []).append(data['data'])
                
        orders = nodes_by_type.get('Order', [])
        if not orders:
            return {"status": "ERROR", "reason": "No Order found"}
        
        order = orders[0]
        payments = nodes_by_type.get('Payment', [])
        refunds = nodes_by_type.get('Refund', [])
        fees = nodes_by_type.get('Fee', [])
        taxes = nodes_by_type.get('Tax', [])
        settlements = nodes_by_type.get('Settlement', [])
        bank_txs = nodes_by_type.get('BankTransaction', [])
        
        audit_trail = {
            "case_id": f"recon_{order.order_id}",
            "order_id": order.order_id,
            "expected_amount": str(order.amount),
            "layers_run": [],
            "decision": "UNRESOLVED",
            "reason": "",
            "confidence": 0.0,
            "ai_investigation": None
        }

        # Calculate Expected Net from System of Record (Order - Refunds - Fees - Taxes)
        total_payment = sum(p.amount for p in payments if p.status == 'CAPTURED')
        total_refund = sum(r.amount for r in refunds if r.status == 'PROCESSED')
        total_fee = sum(f.amount for f in fees)
        total_tax = sum(t.amount for t in taxes)
        
        expected_net = total_payment - total_refund - total_fee - total_tax
        audit_trail["expected_net"] = str(expected_net)
        
        # Calculate Observed Net from Settlements / Bank TX
        settlement_edges = []
        for u, v, data in graph.edges(data=True):
            if data.get('relation') == 'INCLUDED_IN':
                settlement_edges.append(data.get('amount', Decimal('0.00')))
                
        observed_settlement = sum(settlement_edges)
        audit_trail["observed_settlement"] = str(observed_settlement)

        sla_breached = False
        latest_settlement = max([s.initiated_at for s in settlements], default=None) if settlements else None
        if latest_settlement and (self.evaluation_time - latest_settlement).days > self.settlement_window_days:
            sla_breached = True
        
        # --- EVIDENCE CONTRACT & PROOF GENERATION ---
        
        # Determine contract type
        contract_type = "STANDARD_PAYMENT_SETTLEMENT"
        if len(settlements) > 1:
            contract_type = "SPLIT_SETTLEMENT"
        elif refunds:
            contract_type = "PARTIAL_REFUND"

        # Check required evidence
        required_evidence = ["Payment", "Settlement", "BankTransaction"]
        if contract_type == "PARTIAL_REFUND":
            required_evidence.append("Refund")
            
        found_types = set()
        found_ids = []
        if payments:
            found_types.add("Payment")
            found_ids.extend([f"Payment:{p.payment_id}" for p in payments])
        if settlements:
            found_types.add("Settlement")
            found_ids.extend([f"Settlement:{s.settlement_id}" for s in settlements])
        if bank_txs:
            found_types.add("BankTransaction")
            found_ids.extend([f"BankTransaction:{b.bank_transaction_id}" for b in bank_txs])
        if refunds:
            found_types.add("Refund")
            found_ids.extend([f"Refund:{r.refund_id}" for r in refunds])
        
        proof_completeness = sum(1 for req in required_evidence if req in found_types) / len(required_evidence)
        
        # Handle Pending exception (SLA temporal reasoning)
        if not bank_txs and not sla_breached:
            contract_type = "PENDING_SETTLEMENT"
            required_evidence.remove("BankTransaction")
            proof_completeness = sum(1 for req in required_evidence if req in found_types) / len(required_evidence)

        # Contradiction Detection
        conflicting_evidence = []
        if len(bank_txs) > len(settlements) and contract_type != "SPLIT_SETTLEMENT":
             conflicting_evidence.append("More bank transactions than settlements")
        if len(settlements) > len(bank_txs) and len(bank_txs) > 0:
             conflicting_evidence.append("More settlements than bank transactions (Duplicate UTR)")
        if total_refund > total_payment:
             conflicting_evidence.append("Refund exceeds payment amount")
        if len(payments) > len(set(p.payment_id for p in payments)):
             conflicting_evidence.append("Duplicate conflicting payment records found")
        if len(orders) > 1:
             conflicting_evidence.append("Multiple orders merged in single provenance graph")
        
        # Ambiguity detection: Two bank transactions with the same amount but different references
        unique_bank_refs = set(b.reference for b in bank_txs)
        if len(bank_txs) > 1 and len(unique_bank_refs) > 1 and contract_type != "SPLIT_SETTLEMENT":
             conflicting_evidence.append("Ambiguous multiple downstream references found")
             
        # Currency Mismatch
        all_currencies = set()
        if orders: all_currencies.update(o.currency for o in orders)
        if payments: all_currencies.update(p.currency for p in payments)
        if settlements: all_currencies.update(s.currency for s in settlements)
        if bank_txs: all_currencies.update(b.currency for b in bank_txs)
        if refunds: all_currencies.update(r.currency for r in refunds)
        if fees: all_currencies.update(f.currency for f in fees)
        
        if len(all_currencies) > 1:
            conflicting_evidence.append("Currency mismatch across evidence")
             
        proof_validity = "PASS" if not conflicting_evidence else "FAIL"
        
        # Final safety checks
        match_confidence = 0.0
        decision_authority = "NONE"
        final_decision = "UNRESOLVED"
        broken_edges = []
        
        if not bank_txs and sla_breached:
            broken_edges.append("Settlement → BankTransaction")

        # Layer 1: Exact / Layer 2: Composite
        if len(settlements) > 1:
            audit_trail["layers_run"].append("Layer 2: Composite (Split Settlement)")
        else:
            audit_trail["layers_run"].append("Layer 1: Exact")
        if abs(expected_net - observed_settlement) <= self.tolerance:
            match_confidence = 1.0
            if contract_type == "PENDING_SETTLEMENT":
                final_decision = "PENDING"
                decision_authority = "TEMPORAL_DETERMINISTIC"
                audit_trail["reason"] = "Settled but pending bank transaction within SLA."
            elif proof_completeness == 1.0 and proof_validity == "PASS":
                final_decision = "RECONCILED"
                decision_authority = "DETERMINISTIC"
                audit_trail["reason"] = "Exact match across full provenance chain."
            else:
                final_decision = "ESCALATED"
                decision_authority = "INSUFFICIENT_EVIDENCE"
                audit_trail["reason"] = "Insufficient evidence."
                
        # Layer 2: Composite
        if final_decision in ["UNRESOLVED", "ESCALATED"] and max_layer >= 2:
            audit_trail["layers_run"].append("Layer 2: Composite")
            pending_refunds = sum(r.amount for r in refunds if r.status == 'PENDING')
            if not sla_breached and abs(expected_net - pending_refunds - observed_settlement) <= self.tolerance:
                match_confidence = 1.0
                final_decision = "PENDING"
                decision_authority = "COMPOSITE_DETERMINISTIC"
                audit_trail["reason"] = "Reconciled accounting for pending refunds."

        # Layer 4: AI Exception Investigation
        if final_decision in ["UNRESOLVED", "ESCALATED"] and max_layer >= 4:
            audit_trail["layers_run"].append("Layer 4: AI Exception Investigation")
            ai_result = analyze_exception(graph, expected_net, observed_settlement)
            audit_trail["ai_investigation"] = ai_result
            
            if ai_result.get("recommended_action") != "HUMAN_REVIEW_REQUIRED" and float(ai_result.get("confidence", 0)) > 0.9:
                ai_decision = ai_result["recommended_action"]
                match_confidence = float(ai_result["confidence"])
                if ai_decision.startswith("EXCEPTION"):
                    final_decision = ai_decision
                    decision_authority = "AI_DIAGNOSIS"
                    audit_trail["reason"] = "AI Resolved: " + ", ".join(ai_result["likely_causes"])
                elif ai_decision.startswith("RECONCILED"):
                    if proof_validity == "PASS" and proof_completeness == 1.0:
                        if "FEE" in ai_decision and "Fee" not in found_types:
                            final_decision = "ESCALATED"
                            decision_authority = "AI_REJECTED_MISSING_FEE_EVIDENCE"
                        elif "REFUND" in ai_decision and "Refund" not in found_types:
                            final_decision = "ESCALATED"
                            decision_authority = "AI_REJECTED_MISSING_REFUND_EVIDENCE"
                        else:
                            final_decision = ai_decision
                            decision_authority = "AI_RECOVERY"
                        audit_trail["reason"] = "AI Resolved: " + ", ".join(ai_result["likely_causes"])
                    else:
                        final_decision = "ESCALATED"
                        decision_authority = "AI_REJECTED_DUE_TO_INCOMPLETE_PROOF"
                        audit_trail["reason"] = "Insufficient evidence."
            else:
                final_decision = "ESCALATED"
                decision_authority = "HUMAN_REVIEW_REQUIRED"
                audit_trail["reason"] = "Insufficient evidence."
                
        audit_trail["decision"] = final_decision
        audit_trail["decision_authority"] = decision_authority
        audit_trail["proof_completeness"] = proof_completeness
        audit_trail["evidence_contract"] = contract_type
        audit_trail["match_confidence"] = match_confidence
        audit_trail["broken_edges"] = broken_edges
        audit_trail["conflicting_evidence"] = conflicting_evidence
        audit_trail["proof_validity"] = proof_validity
        
        # Build Reconciliation Proof / Proof Gap Report
        audit_trail["proof_certificate"] = {
            "case_id": audit_trail["case_id"],
            "expected_net": str(expected_net),
            "observed_settlement": str(observed_settlement),
            "evidence_contract": {
                "type": contract_type,
                "required": required_evidence,
                "found_types": list(found_types),
                "cited_evidence": found_ids
            },
            "proof_completeness": proof_completeness,
            "temporal_checks": "PASS" if not sla_breached else "FAIL",
            "decision": final_decision,
            "decision_authority": decision_authority,
            "proof_validity": proof_validity
        }
        
        if final_decision in ["ESCALATED", "HUMAN_REVIEW_REQUIRED", "UNRESOLVED"]:
            audit_trail["proof_gap_report"] = {
                "reason": "Mathematical consistency exists but downstream evidence is missing." if match_confidence > 0.9 else "Accounting mismatch.",
                "broken_edges": broken_edges,
                "conflicting_evidence": conflicting_evidence
            }
            
        return audit_trail
