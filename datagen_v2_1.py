import random
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Tuple, Dict
from models import Order, Payment, Refund, Fee, Tax, Settlement, BankTransaction, SettlementItem, LedgerEntry

def generate_case_v2_1(i: int, scenario: str, base_time: datetime, as_of_time: datetime) -> Tuple[List, Dict]:
    records = []
    order_id = str(i)
    
    amount = Decimal(random.randint(100, 50000))
    fee_amt = (amount * Decimal('0.02')).quantize(Decimal('0.01'))
    tax_amt = (fee_amt * Decimal('0.18')).quantize(Decimal('0.01'))
    
    # NO RANDOM JITTER. Deterministic increment.
    case_index = i - 30000
    created_at = base_time + timedelta(minutes=case_index*5)
    
    # 1. System of Record
    order = Order(order_id=order_id, customer_id=f"cust_{i%500}", amount=amount, created_at=created_at, status="COMPLETED")
    payment = Payment(payment_id=f"pay_{i}", order_id=order_id, amount=amount, captured_at=created_at + timedelta(seconds=10), status="CAPTURED", method="UPI")
    fee = Fee(fee_id=f"fee_{i}", payment_id=payment.payment_id, type="GATEWAY", amount=fee_amt, created_at=created_at + timedelta(seconds=11))
    tax = Tax(tax_id=f"tax_{i}", payment_id=payment.payment_id, type="GST", amount=tax_amt, created_at=created_at + timedelta(seconds=11))
    
    records.extend([order, payment, fee, tax])
    expected_settlement = amount - fee_amt - tax_amt
    
    items = []
    initiated_at = created_at + timedelta(days=1)
    
    if scenario == "CLEAN":
        settlement = Settlement(settlement_id=f"set_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR{i}")
        items.append(SettlementItem(item_id=f"si_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        bank_tx = BankTransaction(bank_transaction_id=f"btx_{i}", amount=expected_settlement, timestamp=initiated_at + timedelta(hours=2), reference=settlement.reference, direction="CREDIT")
        ledger = LedgerEntry(ledger_entry_id=f"led_{i}", bank_transaction_id=bank_tx.bank_transaction_id, account="SETTLEMENT_RECEIVABLE", amount=expected_settlement, type="CREDIT", timestamp=bank_tx.timestamp)
        records.extend([settlement, bank_tx, ledger])
        
    elif scenario == "PARTIAL_REFUND":
        refund_amt = (expected_settlement * Decimal('0.5')).quantize(Decimal('0.01'))
        refund = Refund(refund_id=f"ref_{i}", payment_id=payment.payment_id, amount=refund_amt, created_at=created_at + timedelta(hours=5), status="PROCESSED")
        final_settlement = expected_settlement - refund_amt
        settlement = Settlement(settlement_id=f"set_{i}", amount=final_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR{i}")
        
        items.append(SettlementItem(item_id=f"si_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        
        bank_tx = BankTransaction(bank_transaction_id=f"btx_{i}", amount=final_settlement, timestamp=initiated_at + timedelta(hours=2), reference=settlement.reference, direction="CREDIT")
        ledger = LedgerEntry(ledger_entry_id=f"led_{i}", bank_transaction_id=bank_tx.bank_transaction_id, account="SETTLEMENT_RECEIVABLE", amount=final_settlement, type="CREDIT", timestamp=bank_tx.timestamp)
        records.extend([refund, settlement, bank_tx, ledger])
        
    elif scenario == "SPLIT_SETTLEMENT":
        part1 = expected_settlement // 2
        part2 = expected_settlement - part1
        
        set1 = Settlement(settlement_id=f"set_{i}_a", amount=part1, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR{i}a")
        set2 = Settlement(settlement_id=f"set_{i}_b", amount=part2, status="COMPLETED", initiated_at=initiated_at + timedelta(days=1), reference=f"UTR{i}b")
        items.extend([
            SettlementItem(item_id=f"si_{i}_a", settlement_id=set1.settlement_id, payment_id=payment.payment_id, amount=part1),
            SettlementItem(item_id=f"si_{i}_b", settlement_id=set2.settlement_id, payment_id=payment.payment_id, amount=part2)
        ])
        
        b1 = BankTransaction(bank_transaction_id=f"btx_{i}a", amount=part1, timestamp=set1.initiated_at + timedelta(hours=2), reference=set1.reference, direction="CREDIT")
        b2 = BankTransaction(bank_transaction_id=f"btx_{i}b", amount=part2, timestamp=set2.initiated_at + timedelta(hours=2), reference=set2.reference, direction="CREDIT")
        
        l1 = LedgerEntry(ledger_entry_id=f"led_{i}a", bank_transaction_id=b1.bank_transaction_id, account="SETTLEMENT_RECEIVABLE", amount=part1, type="CREDIT", timestamp=b1.timestamp)
        l2 = LedgerEntry(ledger_entry_id=f"led_{i}b", bank_transaction_id=b2.bank_transaction_id, account="SETTLEMENT_RECEIVABLE", amount=part2, type="CREDIT", timestamp=b2.timestamp)
        
        records.extend([set1, set2, b1, b2, l1, l2])

    elif scenario == "DELAYED_SETTLEMENT_EXCEPTION":
        # Settlement age > SLA (e.g. 5 days ago)
        initiated_at = as_of_time - timedelta(days=5)
        # Fix order causality to be proper (e.g. 6 days ago)
        order.created_at = initiated_at - timedelta(days=1)
        payment.captured_at = order.created_at + timedelta(seconds=10)
        fee.created_at = payment.captured_at
        tax.created_at = payment.captured_at
        settlement = Settlement(settlement_id=f"set_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR{i}")
        items.append(SettlementItem(item_id=f"si_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        records.append(settlement)
        # Missing downstream bank tx
        
    elif scenario == "PENDING_BANK_SLA_SAFE":
        # Settlement age <= SLA (e.g. 1 day ago)
        initiated_at = as_of_time - timedelta(days=1)
        order.created_at = initiated_at - timedelta(days=1)
        payment.captured_at = order.created_at + timedelta(seconds=10)
        fee.created_at = payment.captured_at
        tax.created_at = payment.captured_at
        settlement = Settlement(settlement_id=f"set_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR{i}")
        items.append(SettlementItem(item_id=f"si_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        records.append(settlement)
        # Missing downstream bank tx

    elif scenario == "MISSING_FEE_EVIDENCE":
        records.remove(fee)
        settlement = Settlement(settlement_id=f"set_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR{i}")
        items.append(SettlementItem(item_id=f"si_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        bank_tx = BankTransaction(bank_transaction_id=f"btx_{i}", amount=expected_settlement, timestamp=initiated_at + timedelta(hours=2), reference=settlement.reference, direction="CREDIT")
        ledger = LedgerEntry(ledger_entry_id=f"led_{i}", bank_transaction_id=bank_tx.bank_transaction_id, account="SETTLEMENT_RECEIVABLE", amount=expected_settlement, type="CREDIT", timestamp=bank_tx.timestamp)
        records.extend([settlement, bank_tx, ledger])
        

    elif scenario == "CONSOLIDATED_SETTLEMENT_N_TO_1":
        amount2 = Decimal('500.00')
        fee_amt2 = (amount2 * Decimal('0.02')).quantize(Decimal('0.01'))
        tax_amt2 = (fee_amt2 * Decimal('0.18')).quantize(Decimal('0.01'))
        order2 = Order(order_id=order_id+"_2", customer_id=f"cust_{i%500}", amount=amount2, created_at=created_at, status="COMPLETED")
        payment2 = Payment(payment_id=f"pay_{i}_2", order_id=order_id+"_2", amount=amount2, captured_at=created_at, status="CAPTURED", method="UPI")
        fee2 = Fee(fee_id=f"fee_{i}_2", payment_id=payment2.payment_id, type="GATEWAY", amount=fee_amt2, created_at=created_at)
        tax2 = Tax(tax_id=f"tax_{i}_2", payment_id=payment2.payment_id, type="GST", amount=tax_amt2, created_at=created_at)
        
        expected2 = amount2 - fee_amt2 - tax_amt2
        total_set = expected_settlement + expected2
        
        settlement = Settlement(settlement_id=f"set_{i}", amount=total_set, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR{i}")
        items.extend([
            SettlementItem(item_id=f"si_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement),
            SettlementItem(item_id=f"si_{i}_2", settlement_id=settlement.settlement_id, payment_id=payment2.payment_id, amount=expected2)
        ])
        bank_tx = BankTransaction(bank_transaction_id=f"btx_{i}", amount=total_set, timestamp=initiated_at, reference=settlement.reference, direction="CREDIT")
        records.extend([order2, payment2, fee2, tax2, settlement, bank_tx])
        
    elif scenario == "CONTRADICTORY_FEE_RECORDS":
        fee2 = Fee(fee_id=f"fee_dup_{i}", payment_id=payment.payment_id, type="GATEWAY", amount=Decimal('99.99'), created_at=created_at)
        records.append(fee2)
        settlement = Settlement(settlement_id=f"set_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR{i}")
        items.append(SettlementItem(item_id=f"si_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        bank_tx = BankTransaction(bank_transaction_id=f"btx_{i}", amount=expected_settlement, timestamp=initiated_at, reference=settlement.reference, direction="CREDIT")
        records.extend([settlement, bank_tx])

    else: # UNRESOLVABLE
        wrong_amount = (expected_settlement - Decimal('145.22')).quantize(Decimal('0.01'))
        if wrong_amount < 0: wrong_amount = Decimal('100.00')
        settlement = Settlement(settlement_id=f"set_{i}", amount=wrong_amount, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR{i}")
        items.append(SettlementItem(item_id=f"si_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=wrong_amount))
        bank_tx = BankTransaction(bank_transaction_id=f"btx_{i}", amount=wrong_amount, timestamp=initiated_at + timedelta(hours=2), reference=settlement.reference, direction="CREDIT")
        ledger = LedgerEntry(ledger_entry_id=f"led_{i}", bank_transaction_id=bank_tx.bank_transaction_id, account="SETTLEMENT_RECEIVABLE", amount=wrong_amount, type="CREDIT", timestamp=bank_tx.timestamp)
        records.extend([settlement, bank_tx, ledger])

    records.extend(items)
    
    return records, {"order_id": order_id, "ground_truth": scenario}

def generate_adversarial_case_v2_1(i: int, scenario: str, base_time: datetime, as_of_time: datetime) -> Tuple[List, Dict]:
    records = []
    order_id = f"adv_{i}"
    
    amount = Decimal(random.randint(100, 50000))
    fee_amt = (amount * Decimal('0.02')).quantize(Decimal('0.01'))
    tax_amt = (fee_amt * Decimal('0.18')).quantize(Decimal('0.01'))
    
    case_index = i - 30000
    created_at = base_time + timedelta(minutes=case_index*5)
    
    order = Order(order_id=order_id, customer_id=f"cust_adv_{i%100}", amount=amount, created_at=created_at, status="COMPLETED")
    payment = Payment(payment_id=f"pay_adv_{i}", order_id=order_id, amount=amount, captured_at=created_at + timedelta(seconds=10), status="CAPTURED", method="UPI")
    fee = Fee(fee_id=f"fee_adv_{i}", payment_id=payment.payment_id, type="GATEWAY", amount=fee_amt, created_at=created_at + timedelta(seconds=11))
    tax = Tax(tax_id=f"tax_adv_{i}", payment_id=payment.payment_id, type="GST", amount=tax_amt, created_at=created_at + timedelta(seconds=11))
    
    records.extend([order, payment, fee, tax])
    expected_settlement = amount - fee_amt - tax_amt
    
    # We want these cases to generally evaluate cleanly in terms of timestamps.
    # We'll make them 2 days old.
    initiated_at = created_at + timedelta(days=1)
    
    items = []
    
    if scenario == "ADV_SAME_AMOUNT_WRONG_TX":
        # Target within SLA (PENDING is expected)
        initiated_at = as_of_time - timedelta(days=1)
        order.created_at = initiated_at - timedelta(days=1)
        payment.captured_at = order.created_at + timedelta(seconds=10)
        fee.created_at = payment.captured_at
        tax.created_at = payment.captured_at
        
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        records.append(settlement)
        
        unrelated_btx = BankTransaction(bank_transaction_id=f"btx_adv_wrong_{i}", amount=expected_settlement, timestamp=initiated_at + timedelta(hours=2), reference=f"UTR_UNRELATED_{i}", direction="CREDIT")
        records.append(unrelated_btx)

    elif scenario == "ADV_WRONG_PERFECT_FEE":
        records.remove(fee)
        wrong_fee = Fee(fee_id=f"fee_adv_wrong_{i}", payment_id=f"pay_adv_other_{i}", type="GATEWAY", amount=fee_amt, created_at=created_at)
        records.append(wrong_fee)
        
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        bank_tx = BankTransaction(bank_transaction_id=f"btx_adv_{i}", amount=expected_settlement, timestamp=initiated_at + timedelta(hours=2), reference=settlement.reference, direction="CREDIT")
        records.extend([settlement, bank_tx])

    elif scenario == "ADV_DUPLICATE_UTR":
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_dup_{i}")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        settlement2 = Settlement(settlement_id=f"set_adv_wrong_{i}", amount=expected_settlement+100, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_dup_{i}")
        bank_tx = BankTransaction(bank_transaction_id=f"btx_adv_{i}", amount=expected_settlement, timestamp=initiated_at + timedelta(hours=2), reference=f"UTR_adv_dup_{i}", direction="CREDIT")
        records.extend([settlement, settlement2, bank_tx])
        
    elif scenario == "ADV_DUPLICATE_PAYMENT":
        conflicting_payment = Payment(payment_id=payment.payment_id, order_id=order_id, amount=amount + Decimal('50.00'), captured_at=created_at + timedelta(seconds=12), status="CAPTURED", method="UPI")
        records.append(conflicting_payment)
        
    elif scenario == "ADV_MULTI_CURRENCY_LURE":
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        bank_tx = BankTransaction(bank_transaction_id=f"btx_adv_{i}", amount=expected_settlement, currency="USD", timestamp=initiated_at, reference=settlement.reference, direction="CREDIT")
        records.extend([settlement, bank_tx])
        
    elif scenario == "ADV_TIMESTAMP_LURE":
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        bank_tx = BankTransaction(bank_transaction_id=f"btx_adv_{i}", amount=expected_settlement, timestamp=initiated_at + timedelta(days=60), reference=settlement.reference, direction="CREDIT")
        records.extend([settlement, bank_tx])
        
    elif scenario == "ADV_WRONG_REFUND_PERFECT_DISCREPANCY":
        # Discrepancy is 50. But refund is linked to completely unrelated payment.
        wrong_amount = expected_settlement - Decimal('50.00')
        refund = Refund(refund_id=f"ref_adv_{i}", payment_id=f"pay_adv_other_{i}", amount=Decimal('50.00'), created_at=created_at + timedelta(hours=5), status="PROCESSED")
        records.append(refund)
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=wrong_amount, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement)) # Still original expected
        bank_tx = BankTransaction(bank_transaction_id=f"btx_adv_{i}", amount=wrong_amount, timestamp=initiated_at, reference=settlement.reference, direction="CREDIT")
        records.extend([settlement, bank_tx])
        
    elif scenario == "ADV_MIXED_PROVENANCE_SPLIT":
        part1 = expected_settlement // 2
        part2 = expected_settlement - part1
        set1 = Settlement(settlement_id=f"set_adv_{i}_a", amount=part1, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}a")
        set2 = Settlement(settlement_id=f"set_adv_{i}_b", amount=part2, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}b")
        
        # Link item 1 to correct payment
        items.append(SettlementItem(item_id=f"si_adv_{i}_a", settlement_id=set1.settlement_id, payment_id=payment.payment_id, amount=part1))
        # Link item 2 to completely WRONG payment ID
        items.append(SettlementItem(item_id=f"si_adv_{i}_b", settlement_id=set2.settlement_id, payment_id=f"pay_adv_WRONG_{i}", amount=part2))
        
        b1 = BankTransaction(bank_transaction_id=f"btx_adv_{i}a", amount=part1, timestamp=initiated_at, reference=set1.reference, direction="CREDIT")
        b2 = BankTransaction(bank_transaction_id=f"btx_adv_{i}b", amount=part2, timestamp=initiated_at, reference=set2.reference, direction="CREDIT")
        records.extend([set1, set2, b1, b2])

    elif scenario == "ADV_DUPLICATE_BANK_IMPORT":
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        b1 = BankTransaction(bank_transaction_id=f"btx_adv_{i}_1", amount=expected_settlement, timestamp=initiated_at, reference=settlement.reference, direction="CREDIT")
        b2 = BankTransaction(bank_transaction_id=f"btx_adv_{i}_2", amount=expected_settlement, timestamp=initiated_at, reference=settlement.reference, direction="CREDIT")
        records.extend([settlement, b1, b2])

    elif scenario == "ADV_WRONG_TAX_PERFECT_SIGNATURE":
        records.remove(tax)
        wrong_tax = Tax(tax_id=f"tax_adv_wrong_{i}", payment_id=f"pay_adv_wrong_{i}", type="GST", amount=tax_amt, created_at=created_at)
        records.append(wrong_tax)
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        bank_tx = BankTransaction(bank_transaction_id=f"btx_adv_{i}", amount=expected_settlement, timestamp=initiated_at, reference=settlement.reference, direction="CREDIT")
        records.extend([settlement, bank_tx])

    elif scenario == "ADV_MANY_TO_MANY_COLLISION":
        # Missing downstream, but multiple items mapped to same payment
        settlement1 = Settlement(settlement_id=f"set_adv_{i}_a", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}_a")
        settlement2 = Settlement(settlement_id=f"set_adv_{i}_b", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}_b")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement1.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        items.append(SettlementItem(item_id=f"si_adv_{i}_2", settlement_id=settlement2.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        bank_tx = BankTransaction(bank_transaction_id=f"btx_adv_{i}", amount=expected_settlement, timestamp=initiated_at, reference=settlement1.reference, direction="CREDIT")
        records.extend([settlement1, settlement2, bank_tx])

    elif scenario == "ADV_CUSTOMER_COMPONENT_CONTAMINATION":
        other_order_id = f"adv_other_{i}"
        other_order = Order(order_id=other_order_id, customer_id=order.customer_id, amount=Decimal('500.00'), status="COMPLETED", created_at=created_at)
        records.append(other_order)
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        bank_tx = BankTransaction(bank_transaction_id=f"btx_adv_{i}", amount=expected_settlement, timestamp=initiated_at, reference=settlement.reference, direction="CREDIT")
        records.extend([settlement, bank_tx])

    records.extend(items)
    return records, {"order_id": order_id, "ground_truth": scenario}

def generate_complex_dataset_v2_1() -> Tuple[List, List[Tuple[str, str]], datetime]:
    scenarios_normal = [
        "CLEAN", "PARTIAL_REFUND", "SPLIT_SETTLEMENT", 
        "DELAYED_SETTLEMENT_EXCEPTION", "PENDING_BANK_SLA_SAFE",
        "MISSING_FEE_EVIDENCE", "UNRESOLVABLE",
        "CONSOLIDATED_SETTLEMENT_N_TO_1", "CONTRADICTORY_FEE_RECORDS"
    ]
    
    scenarios_adv = [
        "ADV_SAME_AMOUNT_WRONG_TX", "ADV_WRONG_PERFECT_FEE", 
        "ADV_DUPLICATE_UTR", "ADV_DUPLICATE_PAYMENT",
        "ADV_MULTI_CURRENCY_LURE", "ADV_TIMESTAMP_LURE",
        "ADV_WRONG_REFUND_PERFECT_DISCREPANCY", "ADV_MIXED_PROVENANCE_SPLIT",
        "ADV_DUPLICATE_BANK_IMPORT", "ADV_WRONG_TAX_PERFECT_SIGNATURE",
        "ADV_MANY_TO_MANY_COLLISION", "ADV_CUSTOMER_COMPONENT_CONTAMINATION"
    ]

    all_records = []
    all_cases = []
    
    # Deterministic base_time and global as_of_time
    base_time = datetime(2026, 8, 1, 10, 0, 0)
    as_of_time = datetime(2026, 8, 15, 12, 0, 0)
    
    i = 30000
    for scenario in scenarios_normal:
        for _ in range(5):
            records, case_meta = generate_case_v2_1(i, scenario, base_time, as_of_time)
            all_records.extend(records)
            all_cases.append((case_meta["order_id"], case_meta["ground_truth"]))
            i += 1
            
    for scenario in scenarios_adv:
        for _ in range(5):
            records, case_meta = generate_adversarial_case_v2_1(i, scenario, base_time, as_of_time)
            all_records.extend(records)
            all_cases.append((case_meta["order_id"], case_meta["ground_truth"]))
            i += 1
            
    return all_records, all_cases, as_of_time
