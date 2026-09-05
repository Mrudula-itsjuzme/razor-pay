from datetime import datetime, timedelta
import networkx as nx
from decimal import Decimal
from typing import Dict, Any, List, Optional
from ai_agent import analyze_exception
from models import SettlementItem

class ReconciliationEngine:
    def __init__(self, tolerance: Decimal = Decimal('0.00'), settlement_window_days: int = 3):
        self.tolerance = tolerance
        self.settlement_window_days = settlement_window_days

    def authorize_closure(
        self,
        accounting_valid: bool,
        evidence_contract_valid: bool,
        provenance_valid: bool,
        temporal_valid: bool,
        contradiction_valid: bool,
        currency_valid: bool,
        proof_complete: bool
    ) -> bool:
        """The single authoritative closure gate."""
        return (
            accounting_valid and
            evidence_contract_valid and
            provenance_valid and
            temporal_valid and
            contradiction_valid and
            currency_valid and
            proof_complete
        )

    def reconcile_order(self, graph: nx.DiGraph, max_layer: int = 4, target_order_id: Optional[str] = None, as_of_time: Optional[datetime] = None) -> Dict[str, Any]:
        evaluation_time = as_of_time or datetime.now()

        nodes_by_type = {}
        for n, data in graph.nodes(data=True):
            t = data.get('type')
            if t and 'data' in data:
                nodes_by_type.setdefault(t, []).append((n, data['data'], data.get('is_target_evidence', True)))

        orders = [d for n, d, target in nodes_by_type.get('Order', []) if target]
        if target_order_id:
            orders = [o for o in orders if o.order_id == target_order_id]

        if not orders:
            return {"status": "ERROR", "reason": "No Order found"}

        order = orders[0]

        # Target Evidence scoped to this order
        payments = [d for n, d, target in nodes_by_type.get('Payment', []) if target and d.order_id == order.order_id]
        target_payment_ids = set(p.payment_id for p in payments)

        refunds = [d for n, d, target in nodes_by_type.get('Refund', []) if target and d.payment_id in target_payment_ids]
        fees = [d for n, d, target in nodes_by_type.get('Fee', []) if target and d.payment_id in target_payment_ids]
        taxes = [d for n, d, target in nodes_by_type.get('Tax', []) if target and d.payment_id in target_payment_ids]

        target_settlement_ids = set()
        for u, v, data in graph.edges(data=True):
            if data.get('relation') == 'INCLUDED_IN':
                if u.startswith("payment_") and u.replace("payment_", "") in target_payment_ids:
                    target_settlement_ids.add(v.replace("settlement_", ""))
                elif u.startswith("refund_") and u.replace("refund_", "") in [r.refund_id for r in refunds]:
                    target_settlement_ids.add(v.replace("settlement_", ""))

        settlements = [d for n, d, target in nodes_by_type.get('Settlement', []) if target and d.settlement_id in target_settlement_ids]

        target_bank_tx_ids = set()
        for u, v, data in graph.edges(data=True):
            if data.get('relation') == 'CREDITED_AS':
                if u.startswith("settlement_") and u.replace("settlement_", "") in target_settlement_ids:
                    target_bank_tx_ids.add(v.replace("bank_tx_", ""))

        bank_txs = [d for n, d, target in nodes_by_type.get('BankTransaction', []) if target and d.bank_transaction_id in target_bank_tx_ids]

        audit_trail = {
            "case_id": f"recon_{order.order_id}",
            "order_id": order.order_id,
            "expected_amount": str(order.amount),
            "layers_run": ["Layer 1: Exact", "Layer 2: Composite", "Layer 4: AI Exception Investigation"],
            "decision": "UNRESOLVED",
            "reason": "",
            "confidence": 0.0,
            "ai_investigation": None
        }

        # Calculate Expected Net from System of Record
        total_payment = sum(p.amount for p in payments if p.status == 'CAPTURED')
        total_refund = sum(r.amount for r in refunds if r.status == 'PROCESSED')
        total_fee = sum(f.amount for f in fees)
        total_tax = sum(t.amount for t in taxes)

        expected_net = total_payment - total_refund - total_fee - total_tax
        audit_trail["expected_net"] = str(expected_net)

        # Calculate Observed Net
        my_item_total = Decimal('0.00')
        refund_item_abs_total = Decimal('0.00')

        for u, v, data in graph.edges(data=True):
            if data.get('relation') == 'INCLUDED_IN' and v.replace("settlement_", "") in target_settlement_ids:
                amt = data.get('amount', Decimal('0.00'))
                if u.startswith("payment_") and u.replace("payment_", "") in target_payment_ids:
                    my_item_total += amt
                elif u.startswith("refund_") and u.replace("refund_", "") in [r.refund_id for r in refunds]:
                    my_item_total += amt
                    refund_item_abs_total += abs(amt)

        unitemized_refunds = total_refund - refund_item_abs_total
        net_observed = my_item_total - unitemized_refunds
        audit_trail["observed_settlement"] = str(net_observed)

        accounting_valid = (abs(expected_net - net_observed) <= self.tolerance)

        # Temporal & Causal Validation
        temporal_valid = True
        temporal_exception_subtype = None
        sla_breached = False

        for o in orders:
            if o.created_at > evaluation_time:
                temporal_valid = False; temporal_exception_subtype = "FUTURE_DATED_EVIDENCE"
            for p in payments:
                if p.captured_at < o.created_at:
                    temporal_valid = False; temporal_exception_subtype = "CAUSAL_ORDER_VIOLATION"
                for s in settlements:
                    if s.initiated_at < p.captured_at:
                        temporal_valid = False; temporal_exception_subtype = "CAUSAL_ORDER_VIOLATION"
                for r in refunds:
                    if r.created_at < p.captured_at:
                        temporal_valid = False; temporal_exception_subtype = "CAUSAL_ORDER_VIOLATION"

        for s in settlements:
            if s.initiated_at > evaluation_time:
                temporal_valid = False; temporal_exception_subtype = "FUTURE_DATED_EVIDENCE"
            s_bank_txs = [b for b in bank_txs if graph.has_edge(f"settlement_{s.settlement_id}", f"bank_tx_{b.bank_transaction_id}")]
            for b in s_bank_txs:
                if b.timestamp > evaluation_time:
                    temporal_valid = False; temporal_exception_subtype = "FUTURE_DATED_EVIDENCE"
                if b.timestamp < s.initiated_at:
                    temporal_valid = False; temporal_exception_subtype = "CAUSAL_ORDER_VIOLATION"

        latest_settlement = max([s.initiated_at for s in settlements], default=None) if settlements else None
        if latest_settlement:
            delta = (evaluation_time - latest_settlement).total_seconds() / 86400.0
            if delta < 0:
                temporal_valid = False; temporal_exception_subtype = "FUTURE_DATED_EVIDENCE"
            elif not bank_txs and delta > self.settlement_window_days and temporal_valid:
                temporal_valid = False; temporal_exception_subtype = "SETTLEMENT_SLA_BREACHED"
                sla_breached = True

        # Evidence Contract validation
        contract_type = "SETTLEMENT_TO_BANK"
        inferred_adjustment = abs(expected_net - net_observed) > self.tolerance
        if len(settlements) > 1:
            contract_type = "SPLIT_SETTLEMENT"
        elif refunds:
            contract_type = "PARTIAL_REFUND"
        elif fees or taxes or inferred_adjustment:
            contract_type = "FULL_LIFECYCLE"
        elif total_refund > 0:
            contract_type = "PARTIAL_REFUND"

        required_evidence = ["Payment", "Settlement", "BankTransaction"]
        if contract_type == "PARTIAL_REFUND":
            required_evidence.append("Refund")
        if contract_type == "FULL_LIFECYCLE":
            if fees or total_fee > 0 or inferred_adjustment:
                required_evidence.append("Fee")
            if taxes or total_tax > 0 or inferred_adjustment:
                required_evidence.append("Tax")
        if contract_type == "PENDING_SETTLEMENT":
            required_evidence = ["Payment", "Settlement"]

        required_evidence = list(dict.fromkeys(required_evidence))

        evidence_slots = {}
        found_ids = []
        found_types = set()

        # Helper to validate bank txs
        def is_valid_bank_tx(b, s_list):
            if not s_list: return False
            for s in s_list:
                if not graph.has_edge(f"settlement_{s.settlement_id}", f"bank_tx_{b.bank_transaction_id}"):
                    continue
                if b.reference != s.reference:
                    return False
                # Check sum of all bank txs for this settlement matches settlement amount
                s_bank_txs = [bx for bx in bank_txs if graph.has_edge(f"settlement_{s.settlement_id}", f"bank_tx_{bx.bank_transaction_id}")]
                b_total = sum(bx.amount for bx in s_bank_txs)
                if abs(s.amount - b_total) > self.tolerance:
                    return False

            # Ensure not claimed by unrelated settlements
            linked_settlements = [u for u, v, data in graph.edges(data=True) if v == f"bank_tx_{b.bank_transaction_id}" and data.get('relation') == 'CREDITED_AS']
            if len(linked_settlements) > 1:
                return False
            return True

        # Process each required type
        # Payment
        valid_payments = [p for p in payments if p.order_id == order.order_id]
        evidence_slots["Payment"] = {
            "required_type": "Payment",
            "candidate_ids": [p.payment_id for p in payments],
            "valid_target_ids": [p.payment_id for p in valid_payments],
            "satisfied": len(valid_payments) > 0,
            "reason": "Valid payments found" if valid_payments else "No valid payment for order"
        }
        if valid_payments:
            found_types.add("Payment")
            found_ids.extend([f"Payment:{p.payment_id}" for p in valid_payments])

        # Refund
        if "Refund" in required_evidence:
            valid_refunds = [r for r in refunds if r.payment_id in target_payment_ids]
            evidence_slots["Refund"] = {
                "required_type": "Refund",
                "candidate_ids": [r.refund_id for r in refunds],
                "valid_target_ids": [r.refund_id for r in valid_refunds],
                "satisfied": len(valid_refunds) > 0,
                "reason": "Valid refunds found" if valid_refunds else "No valid refund for payment"
            }
            if valid_refunds:
                found_types.add("Refund")
                found_ids.extend([f"Refund:{r.refund_id}" for r in valid_refunds])

        # Fee
        if "Fee" in required_evidence:
            valid_fees = [f for f in fees if f.payment_id in target_payment_ids]
            evidence_slots["Fee"] = {
                "required_type": "Fee",
                "candidate_ids": [f.fee_id for f in fees],
                "valid_target_ids": [f.fee_id for f in valid_fees],
                "satisfied": len(valid_fees) > 0,
                "reason": "Valid fee evidence found" if valid_fees else "No valid fee evidence for payment"
            }
            if valid_fees:
                found_types.add("Fee")
                found_ids.extend([f"Fee:{f.fee_id}" for f in valid_fees])

        # Tax
        if "Tax" in required_evidence:
            valid_taxes = [t for t in taxes if t.payment_id in target_payment_ids]
            evidence_slots["Tax"] = {
                "required_type": "Tax",
                "candidate_ids": [t.tax_id for t in taxes],
                "valid_target_ids": [t.tax_id for t in valid_taxes],
                "satisfied": len(valid_taxes) > 0,
                "reason": "Valid tax evidence found" if valid_taxes else "No valid tax evidence for payment"
            }
            if valid_taxes:
                found_types.add("Tax")
                found_ids.extend([f"Tax:{t.tax_id}" for t in valid_taxes])

        # Settlement
        valid_settlements = settlements
        evidence_slots["Settlement"] = {
            "required_type": "Settlement",
            "candidate_ids": [s.settlement_id for s in settlements],
            "valid_target_ids": [s.settlement_id for s in valid_settlements],
            "satisfied": len(valid_settlements) > 0,
            "reason": "Valid settlements found" if valid_settlements else "No valid settlement for payment"
        }
        if valid_settlements:
            found_types.add("Settlement")
            found_ids.extend([f"Settlement:{s.settlement_id}" for s in valid_settlements])

        # BankTransaction
        valid_bank_txs = [b for b in bank_txs if is_valid_bank_tx(b, settlements)]

        evidence_slots["BankTransaction"] = {
            "required_type": "BankTransaction",
            "candidate_ids": [b.bank_transaction_id for b in bank_txs],
            "valid_target_ids": [b.bank_transaction_id for b in valid_bank_txs],
            "satisfied": len(valid_bank_txs) > 0,
            "reason": "Valid bank transactions found" if valid_bank_txs else "No valid bank transaction or reference mismatch"
        }

        # SLA adjustments
        if not valid_bank_txs and not sla_breached and temporal_valid and valid_settlements:
            contract_type = "PENDING_SETTLEMENT"
            required_evidence = ["Payment", "Settlement"]
            evidence_slots["BankTransaction"]["satisfied"] = True
            evidence_slots["BankTransaction"]["reason"] = "Pending within SLA"

        if "BankTransaction" in required_evidence and valid_bank_txs:
            found_types.add("BankTransaction")
            found_ids.extend([f"BankTransaction:{b.bank_transaction_id}" for b in valid_bank_txs])

        # Full-life-cycle contracts treat missing fee/tax evidence as a proof gap when
        # the settlement arithmetic implies a deduction but the supporting evidence is not observed.
        if contract_type == "FULL_LIFECYCLE":
            if inferred_adjustment and not any(f.payment_id in target_payment_ids for f in fees):
                required_evidence.append("Fee")
            if inferred_adjustment and not any(t.payment_id in target_payment_ids for t in taxes):
                required_evidence.append("Tax")
            required_evidence = list(dict.fromkeys(required_evidence))

        # Overall Proof Completeness
        satisfied_count = sum(1 for req in required_evidence if evidence_slots.get(req, {}).get("satisfied", False))
        proof_completeness = satisfied_count / len(required_evidence)
        proof_complete = (proof_completeness == 1.0)
        evidence_contract_valid = proof_complete

        # Provenance validity matches the slots logic
        provenance_valid = True
        if not evidence_slots.get("BankTransaction", {}).get("satisfied", False):
            provenance_valid = False


        # Contradictions
        contradiction_valid = True
        conflicting_evidence = []
        exception_types = []
        exception_subtypes = []

        # Check for Duplicate UTR
        for b in bank_txs:
            linked_settlements = [u for u, v, data in graph.edges(data=True) if v == f"bank_tx_{b.bank_transaction_id}" and data.get('relation') == 'CREDITED_AS']
            if len(linked_settlements) > 1:
                contradiction_valid = False
                conflicting_evidence.append("Duplicate bank transaction usage across multiple settlements")
                exception_types.append("CONFLICTING_EVIDENCE")
                exception_subtypes.append("DUPLICATE_UTR")

        # Check for Unexplained Settlement Discrepancy (Wrong Refund Provenance)
        for s in settlements:
            s_items_total = sum(data.get('amount', Decimal('0.00')) for u, v, data in graph.edges(data=True) if v == f"settlement_{s.settlement_id}" and data.get('relation') == 'INCLUDED_IN')
            if abs(s.amount - s_items_total) > self.tolerance:
                if abs(s_items_total - s.amount - unitemized_refunds) > self.tolerance:
                    contradiction_valid = False
                    conflicting_evidence.append(f"Settlement {s.settlement_id} amount {s.amount} does not balance with items {s_items_total} and valid refunds {unitemized_refunds}")
                    exception_types.append("CONFLICTING_EVIDENCE")
                    exception_subtypes.append("WRONG_REFUND_PROVENANCE")


        if len(bank_txs) > len(settlements) and contract_type != "SPLIT_SETTLEMENT":
            contradiction_valid = False; conflicting_evidence.append("More bank transactions than settlements"); exception_types.append("CONFLICTING_EVIDENCE"); exception_subtypes.append("DUPLICATE_BANK_IMPORT")
        if len(settlements) > len(bank_txs) and len(bank_txs) > 0:
            contradiction_valid = False; conflicting_evidence.append("More settlements than bank transactions"); exception_types.append("CONFLICTING_EVIDENCE"); exception_subtypes.append("DUPLICATE_SETTLEMENT_REFERENCE")
        if total_refund > total_payment:
            contradiction_valid = False; conflicting_evidence.append("Refund exceeds payment amount"); exception_types.append("ACCOUNTING_MISMATCH"); exception_subtypes.append("ACCOUNTING_IDENTITY_FAILURE")
        if len(payments) > 1 and len(set(p.order_id for p in payments)) == 1:
            contradiction_valid = False; conflicting_evidence.append("Duplicate payment records"); exception_types.append("CONFLICTING_EVIDENCE"); exception_subtypes.append("DUPLICATE_PAYMENT_EVIDENCE")

        fee_map = {}
        for f in fees:
            key = f"{f.payment_id}_{f.type}"
            fee_map[key] = fee_map.get(key, 0) + 1
            if fee_map[key] > 1:
                contradiction_valid = False; conflicting_evidence.append("Duplicate fee records"); exception_types.append("CONFLICTING_EVIDENCE"); exception_subtypes.append("DUPLICATE_FEE_RECORDS"); break

        tax_map = {}
        for t in taxes:
            key = f"{t.payment_id}_{t.type}"
            tax_map[key] = tax_map.get(key, 0) + 1
            if tax_map[key] > 1:
                contradiction_valid = False; conflicting_evidence.append("Duplicate tax records"); exception_types.append("CONFLICTING_EVIDENCE"); exception_subtypes.append("DUPLICATE_TAX_RECORDS"); break

        if len(set(o.customer_id for o in orders)) > 1:
            contradiction_valid = False; conflicting_evidence.append("Mixed provenance"); exception_types.append("AMBIGUOUS_PROVENANCE"); exception_subtypes.append("MIXED_PROVENANCE")

        unique_bank_refs = set(b.reference for b in bank_txs)
        if len(bank_txs) > 1 and len(unique_bank_refs) > 1 and contract_type != "SPLIT_SETTLEMENT":
            contradiction_valid = False; conflicting_evidence.append("Ambiguous downstream references"); exception_types.append("AMBIGUOUS_PROVENANCE"); exception_subtypes.append("AMBIGUOUS_PROVENANCE")

        # Currency Mismatch
        currency_valid = True
        all_currencies = set()
        if orders: all_currencies.update(o.currency for o in orders)
        if payments: all_currencies.update(p.currency for p in payments)
        if settlements: all_currencies.update(s.currency for s in settlements)
        if bank_txs: all_currencies.update(b.currency for b in bank_txs)
        if refunds: all_currencies.update(r.currency for r in refunds)
        if fees: all_currencies.update(f.currency for f in fees)

        if len(all_currencies) > 1:
            currency_valid = False; contradiction_valid = False; conflicting_evidence.append("Currency mismatch"); exception_types.append("CONFLICTING_EVIDENCE"); exception_subtypes.append("CURRENCY_MISMATCH")

        proof_validity = "PASS" if (provenance_valid and temporal_valid and contradiction_valid and currency_valid) else "FAIL"

        # Centralized Closure Gate
        closure_authorized = self.authorize_closure(
            accounting_valid,
            evidence_contract_valid,
            provenance_valid,
            temporal_valid,
            contradiction_valid,
            currency_valid,
            proof_complete
        )

        final_decision = "UNRESOLVED"
        decision_authority = "NONE"
        match_confidence = 0.0

        if closure_authorized:
            match_confidence = 1.0
            if contract_type == "PENDING_SETTLEMENT":
                final_decision = "PENDING"
                decision_authority = "TEMPORAL_DETERMINISTIC"
                audit_trail["reason"] = "Settled but pending bank transaction within SLA."
            else:
                final_decision = "RECONCILED"
                decision_authority = "DETERMINISTIC"
                audit_trail["reason"] = "Exact match across full provenance chain."

        # Layer 4 AI (Restricted to investigation only)
        if not closure_authorized and max_layer >= 4 and not sla_breached:
            try:
                ai_result = analyze_exception(graph, expected_net, net_observed)
            except Exception:
                ai_result = {"recommended_action": "MANUAL_REVIEW_REQUIRED (AI Unavailable)"}
            audit_trail["ai_investigation"] = ai_result
            final_decision = "ESCALATED"
            decision_authority = "HUMAN_REVIEW_REQUIRED"
            audit_trail["reason"] = "Insufficient evidence. " + (ai_result.get("recommended_action", ""))

        elif not closure_authorized:
            final_decision = "ESCALATED"
            decision_authority = "INSUFFICIENT_EVIDENCE"

        audit_trail["decision"] = final_decision
        audit_trail["decision_authority"] = decision_authority
        audit_trail["proof_completeness"] = proof_completeness
        audit_trail["evidence_contract"] = contract_type
        audit_trail["match_confidence"] = match_confidence
        audit_trail["broken_edges"] = []
        audit_trail["conflicting_evidence"] = conflicting_evidence
        audit_trail["proof_validity"] = proof_validity
        audit_trail["exception_types"] = exception_types
        audit_trail["exception_subtypes"] = exception_subtypes

        audit_trail["proof_certificate"] = {
            "case_id": audit_trail["case_id"],
            "expected_net": str(expected_net),
            "observed_settlement": str(net_observed),
            "evidence_contract": {
                "type": contract_type,
                "required": required_evidence,
                "found_types": list(found_types),
                "cited_evidence": found_ids,
                "evidence_slots": evidence_slots
            },
            "proof_completeness": proof_completeness,
            "temporal_checks": "PASS" if temporal_valid else "FAIL",
            "decision": final_decision,
            "decision_authority": decision_authority,
            "proof_validity": proof_validity
        }

        if not closure_authorized:
            exc_type = "UNRESOLVABLE"
            exc_subtype = "UNKNOWN"
            severity = "HIGH"
            rec_action = "Manual human review required."

            if exception_types:
                exc_type = exception_types[0]
                exc_subtype = exception_subtypes[0]
                severity = "CRITICAL"
                rec_action = "Resolve data conflict before attempting closure."
            elif contract_type == "PENDING_SETTLEMENT" and temporal_valid:
                exc_type = "PENDING_EVIDENCE"
                exc_subtype = "BANK_PENDING_WITHIN_SLA"
                severity = "LOW"
                rec_action = "Wait for settlement window."
            elif not temporal_valid and temporal_exception_subtype:
                exc_type = "TEMPORAL_EXCEPTION"
                exc_subtype = temporal_exception_subtype
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
            elif not accounting_valid:
                exc_type = "ACCOUNTING_MISMATCH"
                exc_subtype = "ACCOUNTING_IDENTITY_FAILURE"
                severity = "HIGH"
                rec_action = "Investigate unexplained accounting difference."
            elif not provenance_valid:
                exc_type = "PROVENANCE_FAILURE"
                exc_subtype = "INVALID_DOWNSTREAM_EVIDENCE"
                severity = "HIGH"
                rec_action = "Verify downstream bank references and amounts."

            audit_trail["exception_details"] = {
                "state": final_decision,
                "exception_type": exc_type,
                "exception_subtype": exc_subtype,
                "severity": severity,
                "financial_exposure": str(expected_net),
                "affected_evidence_ids": found_ids,
                "proof_blockers": conflicting_evidence,
                "recommended_action": rec_action,
                "closure_authorized": closure_authorized,
                "temporal_status": "SLA_BREACHED" if sla_breached else "WITHIN_SLA",
                "contradiction_status": "CONFLICT_DETECTED" if exception_types else "NO_CONFLICT"
            }

            audit_trail["proof_gap_report"] = {
                "reason": "Missing or conflicting evidence blocks automated closure.",
                "broken_edges": [],
                "conflicting_evidence": conflicting_evidence
            }

        return audit_trail
