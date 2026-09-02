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

    def reconcile_order(self, graph: nx.DiGraph, max_layer: int = 4, target_order_id: Optional[str] = None) -> Dict[str, Any]:
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
        if target_order_id:
            orders = [o for o in orders if o.order_id == target_order_id]
            
        if not orders:
            return {"status": "ERROR", "reason": "No Order found"}
        
        order = orders[0]
        
        # Filter payments, refunds, fees, taxes to ONLY those connected to the target order
        payments = [p for p in nodes_by_type.get('Payment', []) if p.order_id == order.order_id]
        target_payment_ids = set(p.payment_id for p in payments)
        refunds = [r for r in nodes_by_type.get('Refund', []) if r.payment_id in target_payment_ids]
        fees = [f for f in nodes_by_type.get('Fee', []) if f.payment_id in target_payment_ids]
        taxes = [t for t in nodes_by_type.get('Tax', []) if t.payment_id in target_payment_ids]
        
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

        temporal_exception_subtype = None
        sla_breached = False
        
        for o in orders:
            if o.created_at > self.evaluation_time:
                temporal_exception_subtype = "FUTURE_DATED_EVIDENCE"
            for p in payments:
                if p.captured_at < o.created_at:
                    temporal_exception_subtype = "CAUSAL_ORDER_VIOLATION"
                for s in settlements:
                    if s.initiated_at < p.captured_at:
                        temporal_exception_subtype = "CAUSAL_ORDER_VIOLATION"
                for r in refunds:
                    if r.created_at < p.captured_at:
                        temporal_exception_subtype = "CAUSAL_ORDER_VIOLATION"

        for s in settlements:
            if s.initiated_at > self.evaluation_time:
                temporal_exception_subtype = "FUTURE_DATED_EVIDENCE"
            for b in bank_txs:
                if b.reference == s.reference and b.timestamp < s.initiated_at:
                    temporal_exception_subtype = "CAUSAL_ORDER_VIOLATION"

        latest_settlement = max([s.initiated_at for s in settlements], default=None) if settlements else None
        if latest_settlement:
            delta = (self.evaluation_time - latest_settlement).total_seconds() / 86400.0
            if delta < 0:
                temporal_exception_subtype = "FUTURE_DATED_EVIDENCE"
            elif delta > self.settlement_window_days and not temporal_exception_subtype:
                temporal_exception_subtype = "SETTLEMENT_SLA_BREACHED"
        
        if temporal_exception_subtype:
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

        # Contradiction Detection - Typed Taxonomy
        conflicting_evidence = []
        exception_types = []
        exception_subtypes = []
        
        # 1. Bank vs Settlement counts
        if len(bank_txs) > len(settlements) and contract_type != "SPLIT_SETTLEMENT":
             conflicting_evidence.append("More bank transactions than settlements")
             exception_types.append("CONFLICTING_EVIDENCE")
             exception_subtypes.append("DUPLICATE_BANK_IMPORT")
        if len(settlements) > len(bank_txs) and len(bank_txs) > 0:
             conflicting_evidence.append("More settlements than bank transactions (Duplicate UTR)")
             exception_types.append("CONFLICTING_EVIDENCE")
             exception_subtypes.append("DUPLICATE_SETTLEMENT_REFERENCE")
             
        # 2. Accounting Identity Failures
        if total_refund > total_payment:
             conflicting_evidence.append("Refund exceeds payment amount")
             exception_types.append("ACCOUNTING_MISMATCH")
             exception_subtypes.append("ACCOUNTING_IDENTITY_FAILURE")
             
        # 3. Duplicate Payment Evidence
        if len(payments) > 1 and len(set(p.order_id for p in payments)) == 1:
             conflicting_evidence.append("Duplicate conflicting payment records found")
             exception_types.append("CONFLICTING_EVIDENCE")
             exception_subtypes.append("DUPLICATE_PAYMENT_EVIDENCE")
             
        # 4. Duplicate Fee / Tax Records
        # Group fees by payment_id and type
        fee_map = {}
        for f in fees:
            key = f"{f.payment_id}_{f.type}"
            fee_map[key] = fee_map.get(key, 0) + 1
            if fee_map[key] > 1:
                conflicting_evidence.append("Duplicate fee records for same payment")
                exception_types.append("CONFLICTING_EVIDENCE")
                exception_subtypes.append("DUPLICATE_FEE_RECORDS")
                break
                
        tax_map = {}
        for t in taxes:
            key = f"{t.payment_id}_{t.type}"
            tax_map[key] = tax_map.get(key, 0) + 1
            if tax_map[key] > 1:
                conflicting_evidence.append("Duplicate tax records for same payment")
                exception_types.append("CONFLICTING_EVIDENCE")
                exception_subtypes.append("DUPLICATE_TAX_RECORDS") # Although TAX_RECORD_MISSING is more expected, this handles duplicate tax
                break
        
        # 5. Mixed Provenance (Multiple customers/unrelated orders incorrectly merged)
        if len(set(o.customer_id for o in orders)) > 1:
            conflicting_evidence.append("Mixed provenance detected")
            exception_types.append("AMBIGUOUS_PROVENANCE")
            exception_subtypes.append("MIXED_PROVENANCE")
        
        # 6. Ambiguity detection
        unique_bank_refs = set(b.reference for b in bank_txs)
        if len(bank_txs) > 1 and len(unique_bank_refs) > 1 and contract_type != "SPLIT_SETTLEMENT":
             conflicting_evidence.append("Ambiguous multiple downstream references found")
             exception_types.append("AMBIGUOUS_PROVENANCE")
             exception_subtypes.append("AMBIGUOUS_PROVENANCE")
             
        # 7. Currency Mismatch
        all_currencies = set()
        if orders: all_currencies.update(o.currency for o in orders)
        if payments: all_currencies.update(p.currency for p in payments)
        if settlements: all_currencies.update(s.currency for s in settlements)
        if bank_txs: all_currencies.update(b.currency for b in bank_txs)
        if refunds: all_currencies.update(r.currency for r in refunds)
        if fees: all_currencies.update(f.currency for f in fees)
        
        if len(all_currencies) > 1:
            conflicting_evidence.append("Currency mismatch across evidence")
            exception_types.append("CONFLICTING_EVIDENCE")
            exception_subtypes.append("CURRENCY_MISMATCH")
             
        proof_validity = "PASS" if not conflicting_evidence else "FAIL"
        audit_trail["exception_types"] = exception_types
        audit_trail["exception_subtypes"] = exception_subtypes
        
        # Final safety checks
        match_confidence = 0.0
        decision_authority = "NONE"
        final_decision = "UNRESOLVED"
        broken_edges = []
        
        if not bank_txs and sla_breached:
            broken_edges.append("Settlement → BankTransaction")

        # Layer 1: Exact
        if len(settlements) > 1:
            audit_trail["layers_run"].append("Layer 2: Composite (Split Settlement)")
        else:
            audit_trail["layers_run"].append("Layer 1: Exact")
            
        # N:1 accounting check: We must verify that our payment's settlement items sum to our expected net.
        my_observed_settlement = Decimal('0.00')
        for u, v, data in graph.edges(data=True):
            if data.get('relation') == 'INCLUDED_IN':
                u_id = u.replace("payment_", "").replace("refund_", "")
                if u_id in target_payment_ids or u.replace("refund_", "") in [r.refund_id for r in refunds]:
                     # Wait, just check if it's our item
                     pass
        
        # Simpler approach: my_observed_settlement is sum of all settlement edges belonging to our payments/refunds
        for u, v, data in graph.edges(data=True):
            if data.get('relation') == 'INCLUDED_IN':
                if u.startswith("payment_") and u.replace("payment_", "") in target_payment_ids:
                    my_observed_settlement += data.get('amount', Decimal('0.00'))
                elif u.startswith("refund_") and u.replace("refund_", "") in [r.refund_id for r in refunds]:
                    my_observed_settlement -= data.get('amount', Decimal('0.00'))
                    
        # For N:1, if the settlement total matches all its items, and our item matches our expected net, it's safe.
        # We also need to check if bank_tx amount matches the full settlement amount.
        settlement_valid = True
        for s in settlements:
            s_items_total = sum(data.get('amount', Decimal('0.00')) for u, v, data in graph.edges(data=True) if v == f"settlement_{s.settlement_id}")
            
            # Allow settlement total to match (items_total - related_refunds)
            s_payments = [u.replace("payment_", "") for u, v, data in graph.edges(data=True) if v == f"settlement_{s.settlement_id}" and u.startswith("payment_")]
            s_related_refunds = sum(r.amount for r in refunds if r.payment_id in s_payments and r.status == 'PROCESSED')
            
            if abs(s.amount - s_items_total) > self.tolerance and abs(s.amount - (s_items_total - s_related_refunds)) > self.tolerance:
                settlement_valid = False
            # Check bank tx
            b_total = sum(b.amount for b in bank_txs if b.reference == s.reference)
            if b_total > 0 and abs(s.amount - b_total) > self.tolerance:
                settlement_valid = False

        if abs(expected_net - (my_observed_settlement - total_refund)) <= self.tolerance and settlement_valid:
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
                
        # Layer 2: Composite (Refunds and splits)
        if final_decision in ["UNRESOLVED", "ESCALATED"] and max_layer >= 2:
            audit_trail["layers_run"].append("Layer 2: Composite")
            
            # Partial Refund Logic: 
            # If refund is processed, expected_net is payment - refund - fee - tax.
            # But the SettlementItem linked to the payment might still be for the full expected amount (payment - fee - tax),
            # while the Settlement node amount is final (payment - refund - fee - tax).
            # The AI proves this by verifying: expected_net == (my_observed_settlement - total_refund)
            # AND the Settlement total matches BankTx total.
            
            refund_math_valid = False
            if contract_type == "PARTIAL_REFUND":
                if abs(expected_net - (my_observed_settlement - total_refund)) <= self.tolerance and settlement_valid:
                    # Make sure the bank transaction actually matches the settlement!
                    if proof_completeness == 1.0 and proof_validity == "PASS":
                        refund_math_valid = True
                        
            if refund_math_valid:
                match_confidence = 1.0
                final_decision = "RECONCILED"
                decision_authority = "COMPOSITE_DETERMINISTIC"
                audit_trail["reason"] = "Reconciled composite refund accounting."
                
            # Pending Refunds
            pending_refunds = sum(r.amount for r in refunds if r.status == 'PENDING')
            if not sla_breached and pending_refunds > 0 and abs(expected_net - pending_refunds - my_observed_settlement) <= self.tolerance:
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
        
        # Build Structured Exception for non-proven cases
        if not final_decision.startswith("RECONCILED"):
            exc_type = "UNRESOLVABLE"
            exc_subtype = "UNKNOWN"
            severity = "HIGH"
            rec_action = "Manual human review required."
            
            # Map based on conditions
            if exception_types:
                # Contradiction detected
                exc_type = exception_types[0]
                exc_subtype = exception_subtypes[0]
                severity = "CRITICAL"
                if exc_subtype == "DUPLICATE_FEE_RECORDS":
                    rec_action = "Verify authoritative fee record before closure."
                elif exc_subtype == "DUPLICATE_SETTLEMENT_REFERENCE":
                    rec_action = "Resolve duplicate settlement reference."
                elif exc_subtype == "CURRENCY_MISMATCH":
                    rec_action = "Obtain explicit FX/conversion evidence. Do not convert automatically."
                else:
                    rec_action = "Resolve data conflict before attempting closure."
            elif final_decision == "PENDING" and not sla_breached:
                exc_type = "PENDING_EVIDENCE"
                exc_subtype = "BANK_PENDING_WITHIN_SLA"
                severity = "LOW"
                rec_action = "Wait for settlement window. No action required yet."
            elif final_decision.startswith("EXCEPTION") or (not bank_txs and sla_breached):
                exc_type = "TEMPORAL_EXCEPTION"
                exc_subtype = temporal_exception_subtype if temporal_exception_subtype else "SETTLEMENT_SLA_BREACHED"
                severity = "HIGH"
                rec_action = "Verify settlement status and retrieve bank confirmation."
            elif "Fee" not in found_types:
                exc_type = "MISSING_EVIDENCE"
                exc_subtype = "FEE_RECORD_MISSING"
                severity = "MEDIUM"
                rec_action = "Retrieve authoritative fee record."
            elif "Tax" not in found_types:
                exc_type = "MISSING_EVIDENCE"
                exc_subtype = "TAX_RECORD_MISSING"
                severity = "MEDIUM"
                rec_action = "Retrieve authoritative tax record."
            elif abs(expected_net - (my_observed_settlement - total_refund)) > self.tolerance:
                exc_type = "ACCOUNTING_MISMATCH"
                exc_subtype = "ACCOUNTING_IDENTITY_FAILURE"
                severity = "HIGH"
                rec_action = "Investigate unexplained accounting difference."
                
            audit_trail["exception_details"] = {
                "state": final_decision,
                "exception_type": exc_type,
                "exception_subtype": exc_subtype,
                "severity": severity,
                "financial_exposure": str(expected_net),
                "affected_evidence_ids": found_ids,
                "proof_blockers": conflicting_evidence + broken_edges,
                "recommended_action": rec_action,
                "closure_authorized": False,
                "temporal_status": "SLA_BREACHED" if sla_breached else "WITHIN_SLA",
                "contradiction_status": "CONFLICT_DETECTED" if exception_types else "NO_CONFLICT"
            }
            
        if final_decision in ["ESCALATED", "HUMAN_REVIEW_REQUIRED", "UNRESOLVED"] or final_decision.startswith("EXCEPTION"):
            audit_trail["proof_gap_report"] = {
                "reason": "Mathematical consistency exists but downstream evidence is missing." if match_confidence > 0.9 else "Accounting mismatch.",
                "broken_edges": broken_edges,
                "conflicting_evidence": conflicting_evidence
            }
            
        return audit_trail
