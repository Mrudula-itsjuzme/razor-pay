import networkx as nx
from models import *
from typing import Dict, Any, List, Optional

class ProvenanceGraph:
    def __init__(self):
        self.g = nx.DiGraph()
        self._undirected_cache = None
        self._dirty = False

    def _mark_dirty(self):
        self._dirty = True

    def _get_undirected(self):
        if self._dirty or self._undirected_cache is None:
            self._undirected_cache = self.g.to_undirected()
            self._dirty = False
        return self._undirected_cache

    def add_order(self, order: Order):
        self._mark_dirty()
        self.g.add_node(f"order_{order.order_id}", type="Order", data=order)
        self.g.add_node(f"customer_{order.customer_id}", type="Customer", id=order.customer_id)
        self.g.add_edge(f"customer_{order.customer_id}", f"order_{order.order_id}", relation="PLACED")

    def add_payment(self, payment: Payment):
        self._mark_dirty()
        self.g.add_node(f"payment_{payment.payment_id}", type="Payment", data=payment)
        self.g.add_edge(f"order_{payment.order_id}", f"payment_{payment.payment_id}", relation="GENERATED")

    def add_refund(self, refund: Refund):
        self._mark_dirty()
        self.g.add_node(f"refund_{refund.refund_id}", type="Refund", data=refund)
        self.g.add_edge(f"payment_{refund.payment_id}", f"refund_{refund.refund_id}", relation="GENERATED")

    def add_fee(self, fee: Fee):
        self._mark_dirty()
        self.g.add_node(f"fee_{fee.fee_id}", type="Fee", data=fee)
        if fee.payment_id:
            self.g.add_edge(f"payment_{fee.payment_id}", f"fee_{fee.fee_id}", relation="INCURRED")
        if fee.settlement_id:
            self.g.add_edge(f"settlement_{fee.settlement_id}", f"fee_{fee.fee_id}", relation="INCURRED")

    def add_tax(self, tax: Tax):
        self._mark_dirty()
        self.g.add_node(f"tax_{tax.tax_id}", type="Tax", data=tax)
        if tax.payment_id:
            self.g.add_edge(f"payment_{tax.payment_id}", f"tax_{tax.tax_id}", relation="INCURRED")
        if tax.settlement_id:
            self.g.add_edge(f"settlement_{tax.settlement_id}", f"tax_{tax.tax_id}", relation="INCURRED")

    def add_settlement(self, settlement: Settlement, items: List[SettlementItem]):
        self._mark_dirty()
        self.g.add_node(f"settlement_{settlement.settlement_id}", type="Settlement", data=settlement)
        for item in items:
            if item.payment_id:
                self.g.add_edge(f"payment_{item.payment_id}", f"settlement_{settlement.settlement_id}", relation="INCLUDED_IN", amount=item.amount)
            if item.refund_id:
                self.g.add_edge(f"refund_{item.refund_id}", f"settlement_{settlement.settlement_id}", relation="INCLUDED_IN", amount=item.amount)

    def add_bank_transaction(self, tx: BankTransaction):
        self._mark_dirty()
        self.g.add_node(f"bank_tx_{tx.bank_transaction_id}", type="BankTransaction", data=tx)
        
    def link_bank_transaction_to_settlement(self, tx_id: str, settlement_id: str):
        self._mark_dirty()
        if f"bank_tx_{tx_id}" in self.g and f"settlement_{settlement_id}" in self.g:
            self.g.add_edge(f"settlement_{settlement_id}", f"bank_tx_{tx_id}", relation="CREDITED_AS")

    def add_ledger_entry(self, entry: LedgerEntry):
        self._mark_dirty()
        self.g.add_node(f"ledger_{entry.ledger_entry_id}", type="LedgerEntry", data=entry)
        
    def link_ledger_to_bank_tx(self, ledger_id: str, tx_id: str):
        self._mark_dirty()
        if f"ledger_{ledger_id}" in self.g and f"bank_tx_{tx_id}" in self.g:
            self.g.add_edge(f"bank_tx_{tx_id}", f"ledger_{ledger_id}", relation="POSTED_AS")

    def get_subgraph_for_order(self, order_id: str) -> nx.DiGraph:
        node = f"order_{order_id}"
        if node not in self.g:
            return nx.DiGraph()
            
        target_nodes = set([node])
        
        # Add Customer (predecessor of Order)
        for pred in self.g.predecessors(node):
            target_nodes.add(pred)
            
        # Target Payments
        payments = [s for s in self.g.successors(node) if s.startswith("payment_")]
        target_nodes.update(payments)
        
        # Target Refunds, Fees, Taxes (successors of Payments)
        for p in payments:
            for s in self.g.successors(p):
                if s.startswith("refund_") or s.startswith("fee_") or s.startswith("tax_"):
                    target_nodes.add(s)
                    
        # Target Settlements (successors of Payments and Refunds via INCLUDED_IN)
        settlements = set()
        for n in list(target_nodes):
            for s in self.g.successors(n):
                if s.startswith("settlement_"):
                    settlements.add(s)
                    target_nodes.add(s)
                    
        # Target BankTransactions (successors of Settlements)
        for s in settlements:
            for btx in self.g.successors(s):
                if btx.startswith("bank_tx_"):
                    target_nodes.add(btx)
                    # Target LedgerEntries
                    for l in self.g.successors(btx):
                        if l.startswith("ledger_"):
                            target_nodes.add(l)
                            
        full_nodes = target_nodes
        
        subgraph = self.g.subgraph(full_nodes).copy()
        for n in subgraph.nodes():
            subgraph.nodes[n]['is_target_evidence'] = True
            
        return subgraph
