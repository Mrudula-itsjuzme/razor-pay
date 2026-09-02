with open("test_system.py", "a") as f:
    f.write("""

def test_temporal_negative_controls():
    g = ProvenanceGraph()
    dt_order = datetime(2026, 8, 10, 10, 0, 0)
    order = Order(order_id="nc1", customer_id="c_nc", amount=Decimal('100.00'), status="COMPLETED", created_at=dt_order)
    payment = Payment(payment_id="p_nc", order_id="nc1", amount=Decimal('100.00'), status="CAPTURED", method="UPI", captured_at=dt_order)
    
    # A. settlement age = 1 day, bank missing -> PENDING
    # Evaluation time is Aug 15. So 1 day age means Aug 14.
    s1 = Settlement(settlement_id="s1", amount=Decimal('100.00'), status="COMPLETED", initiated_at=datetime(2026, 8, 14, 10, 0, 0), reference="UTR1")
    si1 = SettlementItem(item_id="si1", settlement_id="s1", payment_id="p_nc", amount=Decimal('100.00'))
    
    g_a = ProvenanceGraph()
    g_a.add_order(order)
    g_a.add_payment(payment)
    g_a.add_settlement(s1, [si1])
    res_a = engine.reconcile_order(g_a.get_subgraph_for_order("nc1"), target_order_id="nc1", max_layer=4)
    assert res_a["decision"] == "PENDING"
    
    # B. settlement age = SLA exactly -> PENDING
    s2 = Settlement(settlement_id="s2", amount=Decimal('100.00'), status="COMPLETED", initiated_at=datetime(2026, 8, 12, 0, 0, 0), reference="UTR2")
    si2 = SettlementItem(item_id="si2", settlement_id="s2", payment_id="p_nc", amount=Decimal('100.00'))
    
    g_b = ProvenanceGraph()
    g_b.add_order(order)
    g_b.add_payment(payment)
    g_b.add_settlement(s2, [si2])
    # Set engine eval time specifically for boundary test
    old_eval = engine.evaluation_time
    engine.evaluation_time = datetime(2026, 8, 15, 0, 0, 0)
    res_b = engine.reconcile_order(g_b.get_subgraph_for_order("nc1"), target_order_id="nc1", max_layer=4)
    assert res_b["decision"] == "PENDING"
    
    # C. settlement age = SLA + 1 second -> TEMPORAL_EXCEPTION
    engine.evaluation_time = datetime(2026, 8, 15, 0, 0, 1)
    res_c = engine.reconcile_order(g_b.get_subgraph_for_order("nc1"), target_order_id="nc1", max_layer=4)
    assert res_c["exception_details"]["exception_type"] == "TEMPORAL_EXCEPTION"
    assert res_c["exception_details"]["exception_subtype"] == "SETTLEMENT_SLA_BREACHED"
    
    # D. settlement timestamp > as_of_time -> FUTURE_DATED_EVIDENCE
    s4 = Settlement(settlement_id="s4", amount=Decimal('100.00'), status="COMPLETED", initiated_at=datetime(2026, 8, 16, 0, 0, 0), reference="UTR4")
    si4 = SettlementItem(item_id="si4", settlement_id="s4", payment_id="p_nc", amount=Decimal('100.00'))
    g_d = ProvenanceGraph()
    g_d.add_order(order)
    g_d.add_payment(payment)
    g_d.add_settlement(s4, [si4])
    engine.evaluation_time = datetime(2026, 8, 15, 0, 0, 0)
    res_d = engine.reconcile_order(g_d.get_subgraph_for_order("nc1"), target_order_id="nc1", max_layer=4)
    assert res_d["exception_details"]["exception_type"] == "TEMPORAL_EXCEPTION"
    assert res_d["exception_details"]["exception_subtype"] == "FUTURE_DATED_EVIDENCE"
    
    # E. settlement before payment -> CAUSAL_ORDER_VIOLATION
    s5 = Settlement(settlement_id="s5", amount=Decimal('100.00'), status="COMPLETED", initiated_at=datetime(2026, 8, 9, 0, 0, 0), reference="UTR5")
    si5 = SettlementItem(item_id="si5", settlement_id="s5", payment_id="p_nc", amount=Decimal('100.00'))
    g_e = ProvenanceGraph()
    g_e.add_order(order)
    g_e.add_payment(payment)
    g_e.add_settlement(s5, [si5])
    res_e = engine.reconcile_order(g_e.get_subgraph_for_order("nc1"), target_order_id="nc1", max_layer=4)
    assert res_e["exception_details"]["exception_type"] == "TEMPORAL_EXCEPTION"
    assert res_e["exception_details"]["exception_subtype"] == "CAUSAL_ORDER_VIOLATION"
    
    # Restore evaluation time
    engine.evaluation_time = old_eval

def test_adversarial_lure_negative_controls():
    # F, G, H, I
    dt_order = datetime(2026, 8, 10, 10, 0, 0)
    order = Order(order_id="nc2", customer_id="c_nc2", amount=Decimal('100.00'), status="COMPLETED", created_at=dt_order)
    payment = Payment(payment_id="p_nc2", order_id="nc2", amount=Decimal('100.00'), status="CAPTURED", method="UPI", captured_at=dt_order)
    fee = Fee(fee_id="f_nc2", payment_id="p_nc2", type="GATEWAY", amount=Decimal('2.00'), created_at=dt_order)
    tax = Tax(tax_id="t_nc2", payment_id="p_nc2", type="GST", amount=Decimal('0.36'), created_at=dt_order)
    
    expected_amount = Decimal('97.64')
    
    # F. same amount + wrong reference + target within SLA -> PENDING
    s_f = Settlement(settlement_id="s_f", amount=expected_amount, status="COMPLETED", initiated_at=datetime(2026, 8, 14, 10, 0, 0), reference="UTR_F")
    si_f = SettlementItem(item_id="si_f", settlement_id="s_f", payment_id="p_nc2", amount=expected_amount)
    b_f_lure = BankTransaction(bank_transaction_id="b_f_lure", amount=expected_amount, timestamp=datetime(2026, 8, 14, 12, 0, 0), reference="UTR_WRONG", direction="CREDIT")
    
    g_f = ProvenanceGraph()
    g_f.add_order(order)
    g_f.add_payment(payment)
    g_f.add_fee(fee)
    g_f.add_tax(tax)
    g_f.add_settlement(s_f, [si_f])
    g_f.add_bank_transaction(b_f_lure) # Not linked to settlement
    
    res_f = engine.reconcile_order(g_f.get_subgraph_for_order("nc2"), target_order_id="nc2", max_layer=4)
    assert res_f["decision"] == "PENDING"
    assert "b_f_lure" not in str(res_f.get("proof_certificate", {}))
    
    # G. same amount + wrong reference + target outside SLA -> TEMPORAL_EXCEPTION
    s_g = Settlement(settlement_id="s_g", amount=expected_amount, status="COMPLETED", initiated_at=datetime(2026, 8, 10, 10, 0, 0), reference="UTR_G")
    si_g = SettlementItem(item_id="si_g", settlement_id="s_g", payment_id="p_nc2", amount=expected_amount)
    
    g_g = ProvenanceGraph()
    g_g.add_order(order)
    g_g.add_payment(payment)
    g_g.add_fee(fee)
    g_g.add_tax(tax)
    g_g.add_settlement(s_g, [si_g])
    g_g.add_bank_transaction(b_f_lure)
    
    res_g = engine.reconcile_order(g_g.get_subgraph_for_order("nc2"), target_order_id="nc2", max_layer=4)
    assert res_g["exception_details"]["exception_type"] == "TEMPORAL_EXCEPTION"
    
    # H. same amount + correct reference + complete valid evidence -> RECONCILED
    b_h_correct = BankTransaction(bank_transaction_id="b_h_correct", amount=expected_amount, timestamp=datetime(2026, 8, 10, 12, 0, 0), reference="UTR_G", direction="CREDIT")
    g_g.add_bank_transaction(b_h_correct)
    g_g.link_bank_transaction_to_settlement("b_h_correct", "s_g")
    
    res_h = engine.reconcile_order(g_g.get_subgraph_for_order("nc2"), target_order_id="nc2", max_layer=4)
    assert res_h["decision"] == "RECONCILED"
    assert "b_h_correct" in str(res_h.get("proof_certificate", {}))
    # I. unrelated lure ID absent from target proof certificate
    assert "b_f_lure" not in str(res_h.get("proof_certificate", {}))

""")
