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
        
        # Filter explicitly to target evidence to avoid context contamination
        payments = [d for n, d, target in nodes_by_type.get('Payment', []) if target and d.order_id == order.order_id]
        target_payment_ids = set(p.payment_id for p in payments)
        
        refunds = [d for n, d, target in nodes_by_type.get('Refund', []) if target and d.payment_id in target_payment_ids]
        fees = [d for n, d, target in nodes_by_type.get('Fee', []) if target and d.payment_id in target_payment_ids]
        taxes = [d for n, d, target in nodes_by_type.get('Tax', []) if target and d.payment_id in target_payment_ids]
        
        # Find settlements containing our target items
        target_settlement_ids = set()
        for u, v, data in graph.edges(data=True):
            if data.get('relation') == 'INCLUDED_IN':
                if u.startswith("payment_") and u.replace("payment_", "") in target_payment_ids:
                    target_settlement_ids.add(v.replace("settlement_", ""))
                elif u.startswith("refund_") and u.replace("refund_", "") in [r.refund_id for r in refunds]:
                    target_settlement_ids.add(v.replace("settlement_", ""))
                    
        settlements = [d for n, d, target in nodes_by_type.get('Settlement', []) if d.settlement_id in target_settlement_ids]
        
        # Find bank transactions tied to our target settlements
        target_bank_tx_ids = set()
        for u, v, data in graph.edges(data=True):
            if data.get('relation') == 'CREDITED_AS':
                if u.startswith("settlement_") and u.replace("settlement_", "") in target_settlement_ids:
                    target_bank_tx_ids.add(v.replace("bank_tx_", ""))
                    
        bank_txs = [d for n, d, target in nodes_by_type.get('BankTransaction', []) if d.bank_transaction_id in target_bank_tx_ids]
        
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

        # Calculate Expected Net from System of Record
        total_payment = sum(p.amount for p in payments if p.status == 'CAPTURED')
        total_refund = sum(r.amount for r in refunds if r.status == 'PROCESSED')
        total_fee = sum(f.amount for f in fees)
        total_tax = sum(t.amount for t in taxes)
        
        expected_net = total_payment - total_refund - total_fee - total_tax
        audit_trail["expected_net"] = str(expected_net)
        
        # Calculate Observed Net for OUR target items ONLY
        my_observed_settlement = Decimal('0.00')
        for u, v, data in graph.edges(data=True):
            if data.get('relation') == 'INCLUDED_IN' and v.replace("settlement_", "") in target_settlement_ids:
                if u.startswith("payment_") and u.replace("payment_", "") in target_payment_ids:
                    my_observed_settlement += data.get('amount', Decimal('0.00'))
                elif u.startswith("refund_") and u.replace("refund_", "") in [r.refund_id for r in refunds]:
                    # The generator creates positive amounts for refunds, and includes them conceptually.
                    # Wait, refund accounting: if there is an explicit SettlementItem for a refund, its amount is added.
                    # Let's standardize: all amounts in INCLUDED_IN edges are algebraically added. If it's a refund, it should be negative if it deducts from settlement.
                    # Datagen gives amount = expected_settlement for Payment item. And doesn't give a refund item.
                    # If it did, it should just add it algebraically.
                    # Let's do: add all items algebraically.
                    # Wait, the prompt says: "Determine whether refund SettlementItems are: A. already included as negative/net... B. informational while refunds are separately deducted. Choose ONE canonical accounting representation. Then derive manually:"
                    # Let's adopt A: Explicit items are algebraic (amount can be negative or positive), we just sum our items. 
                    # If explicit refund items are absent, my_observed_settlement will not include them. 
                    # If they are absent, my_observed_settlement = Payment SettlementItem. And we know we must subtract total_refund manually to get net.
                    # Actually, if Razorpay standard is: Payment SettlementItem contains gross amount, then Refund is deducted from Settlement total. 
                    # Let's just sum what we observe in explicit items, then subtract what we KNOW we refunded but didn't observe.
                    pass
