def get_expected_evidence(order_id: str, ground_truth: str) -> set:
    """Returns the set of expected valid evidence IDs for a given case."""
    
    # Strip any potential adv prefix to find base ID for ID generation
    # Actually datagen uses the order_id as the case_id directly.
    cid = order_id
    expected = set()
    
    # Base valid IDs
    pay_id = f"Payment:pay_{cid}"
    fee_id = f"Fee:fee_{cid}"
    tax_id = f"Tax:tax_{cid}"
    set_id = f"Settlement:set_{cid}"
    btx_id = f"BankTransaction:btx_{cid}"
    
    if "adv" in cid:
        pay_id = f"Payment:pay_adv_{cid}"
        fee_id = f"Fee:fee_adv_{cid}"
        tax_id = f"Tax:tax_adv_{cid}"
        set_id = f"Settlement:set_adv_{cid}"
        btx_id = f"BankTransaction:btx_adv_{cid}"

    # Default valid sets
    expected.add(pay_id)
    expected.add(fee_id)
    expected.add(tax_id)
    expected.add(set_id)
    expected.add(btx_id)

    if ground_truth == "CLEAN":
        pass
    elif ground_truth == "PARTIAL_REFUND":
        expected.add(f"Refund:ref_{cid}")
    elif ground_truth == "SPLIT_SETTLEMENT":
        expected.remove(set_id)
        expected.remove(btx_id)
        expected.add(f"Settlement:set_{cid}_a")
        expected.add(f"Settlement:set_{cid}_b")
        expected.add(f"BankTransaction:btx_{cid}a")
        expected.add(f"BankTransaction:btx_{cid}b")
    elif ground_truth in ["DELAYED_SETTLEMENT_EXCEPTION", "PENDING_BANK_SLA_SAFE"]:
        expected.remove(btx_id)
    elif ground_truth == "MISSING_FEE_EVIDENCE":
        expected.remove(fee_id)
    elif ground_truth == "CONSOLIDATED_SETTLEMENT_N_TO_1":
        expected.add(f"Payment:pay_{cid}_2")
        expected.add(f"Fee:fee_{cid}_2")
        expected.add(f"Tax:tax_{cid}_2")
    elif ground_truth == "CONTRADICTORY_FEE_RECORDS":
        expected.remove(fee_id) # Duplicate invalidates the real one too for exact match, but actually the real fee IS fee_id. 
        # But wait, we expect the system to cite the real fee? For conflicting records, it shouldn't reconcile anyway.
        expected.add(fee_id)
        
    # Adversarial cases
    elif ground_truth == "ADV_WRONG_PERFECT_FEE":
        expected.remove(fee_id)
    elif ground_truth == "ADV_DUPLICATE_UTR":
        pass
    elif ground_truth == "ADV_MULTI_CURRENCY_LURE":
        pass
    elif ground_truth == "ADV_TIMESTAMP_LURE":
        pass
    elif ground_truth == "ADV_WRONG_REFUND_PERFECT_DISCREPANCY":
        pass
    elif ground_truth == "ADV_MIXED_PROVENANCE_SPLIT":
        expected.remove(set_id)
        expected.remove(btx_id)
        expected.add(f"Settlement:set_adv_{cid}_a")
        expected.add(f"Settlement:set_adv_{cid}_b")
        expected.add(f"BankTransaction:btx_adv_{cid}a")
        expected.add(f"BankTransaction:btx_adv_{cid}b")
    elif ground_truth == "ADV_DUPLICATE_BANK_IMPORT":
        expected.remove(btx_id)
        expected.add(f"BankTransaction:btx_adv_{cid}_1")
    elif ground_truth == "ADV_WRONG_TAX_PERFECT_SIGNATURE":
        expected.remove(tax_id)
    elif ground_truth == "ADV_MANY_TO_MANY_COLLISION":
        expected.remove(set_id)
        expected.add(f"Settlement:set_adv_{cid}_a")
        expected.add(f"Settlement:set_adv_{cid}_b")
    elif ground_truth == "ADV_CUSTOMER_COMPONENT_CONTAMINATION":
        pass

    return expected
