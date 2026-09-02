with open("test_system.py", "a") as f:
    f.write("""

def test_complete_proof_temporal_negative_controls():
    # A complete matching settlement + bank evidence but invalid time
    dt_order = datetime(2026, 8, 10, 10, 0, 0)
    order = Order(order_id="nc3", customer_id="c_nc3", amount=Decimal('100.00'), status="COMPLETED", created_at=dt_order)
    payment = Payment(payment_id="p_nc3", order_id="nc3", amount=Decimal('100.00'), status="CAPTURED", method="UPI", captured_at=dt_order)
    fee = Fee(fee_id="f_nc3", payment_id="p_nc3", type="GATEWAY", amount=Decimal('2.00'), created_at=dt_order)
    tax = Tax(tax_id="t_nc3", payment_id="p_nc3", type="GST", amount=Decimal('0.36'), created_at=dt_order)
    
    expected_amount = Decimal('97.64')
    
    # Base setup
    s_a = Settlement(settlement_id="s_a", amount=expected_amount, status="COMPLETED", initiated_at=datetime(2026, 8, 14, 10, 0, 0), reference="UTR_NC3")
    si_a = SettlementItem(item_id="si_a", settlement_id="s_a", payment_id="p_nc3", amount=expected_amount)
    
    g_a = ProvenanceGraph()
    g_a.add_order(order)
    g_a.add_payment(payment)
    g_a.add_fee(fee)
    g_a.add_tax(tax)
    g_a.add_settlement(s_a, [si_a])
    
    old_eval = engine.evaluation_time
    engine.evaluation_time = datetime(2026, 8, 15, 0, 0, 0)
    
    # A. Bank > as_of_time
    b_a = BankTransaction(bank_transaction_id="b_a", amount=expected_amount, timestamp=datetime(2026, 8, 16, 12, 0, 0), reference="UTR_NC3", direction="CREDIT")
    g_a.add_bank_transaction(b_a)
    g_a.link_bank_transaction_to_settlement("b_a", "s_a")
    
    res_a = engine.reconcile_order(g_a.get_subgraph_for_order("nc3"), target_order_id="nc3", max_layer=4)
    assert res_a["decision"] == "ESCALATED"
    assert res_a["exception_details"]["exception_type"] == "TEMPORAL_EXCEPTION"
    
    # B. Complete matching evidence, but settlement before payment
    s_b = Settlement(settlement_id="s_b", amount=expected_amount, status="COMPLETED", initiated_at=datetime(2026, 8, 9, 10, 0, 0), reference="UTR_B")
    si_b = SettlementItem(item_id="si_b", settlement_id="s_b", payment_id="p_nc3", amount=expected_amount)
    b_b = BankTransaction(bank_transaction_id="b_b", amount=expected_amount, timestamp=datetime(2026, 8, 9, 12, 0, 0), reference="UTR_B", direction="CREDIT")
    
    g_b = ProvenanceGraph()
    g_b.add_order(order)
    g_b.add_payment(payment)
    g_b.add_fee(fee)
    g_b.add_tax(tax)
    g_b.add_settlement(s_b, [si_b])
    g_b.add_bank_transaction(b_b)
    g_b.link_bank_transaction_to_settlement("b_b", "s_b")
    
    res_b = engine.reconcile_order(g_b.get_subgraph_for_order("nc3"), target_order_id="nc3", max_layer=4)
    assert res_b["decision"] == "ESCALATED"
    assert res_b["exception_details"]["exception_type"] == "TEMPORAL_EXCEPTION"
    assert res_b["exception_details"]["exception_subtype"] == "CAUSAL_ORDER_VIOLATION"
    
    # C. Complete matching evidence with valid chronology
    s_c = Settlement(settlement_id="s_c", amount=expected_amount, status="COMPLETED", initiated_at=datetime(2026, 8, 14, 10, 0, 0), reference="UTR_C")
    si_c = SettlementItem(item_id="si_c", settlement_id="s_c", payment_id="p_nc3", amount=expected_amount)
    b_c = BankTransaction(bank_transaction_id="b_c", amount=expected_amount, timestamp=datetime(2026, 8, 14, 12, 0, 0), reference="UTR_C", direction="CREDIT")
    
    g_c = ProvenanceGraph()
    g_c.add_order(order)
    g_c.add_payment(payment)
    g_c.add_fee(fee)
    g_c.add_tax(tax)
    g_c.add_settlement(s_c, [si_c])
    g_c.add_bank_transaction(b_c)
    g_c.link_bank_transaction_to_settlement("b_c", "s_c")
    
    res_c = engine.reconcile_order(g_c.get_subgraph_for_order("nc3"), target_order_id="nc3", max_layer=4)
    assert res_c["decision"] == "RECONCILED"
    
    # D. proof_completeness mathematical check
    assert res_b["proof_completeness"] == 1.0
    assert res_b["exception_details"]["closure_authorized"] is False

    engine.evaluation_time = old_eval
""")
