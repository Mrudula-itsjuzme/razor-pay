import random
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Tuple, Dict
from models import Order, Payment, Refund, Fee, Tax, Settlement, BankTransaction, SettlementItem, LedgerEntry

def generate_case(i: int, scenario: str, base_time: datetime) -> Tuple[List, Dict]:
    records = []
    order_id = str(i)
    
    amount = Decimal(random.randint(100, 50000))
    fee_amt = (amount * Decimal('0.02')).quantize(Decimal('0.01'))
    tax_amt = (fee_amt * Decimal('0.18')).quantize(Decimal('0.01'))
    
    created_at = base_time + timedelta(minutes=i*5)
    
    # 1. System of Record
    order = Order(order_id=order_id, customer_id=f"cust_{i%500}", amount=amount, created_at=created_at, status="COMPLETED")
    payment = Payment(payment_id=f"pay_{i}", order_id=order_id, amount=amount, captured_at=created_at + timedelta(seconds=10), status="CAPTURED", method="UPI")
    fee = Fee(fee_id=f"fee_{i}", payment_id=payment.payment_id, type="GATEWAY", amount=fee_amt, created_at=created_at + timedelta(seconds=11))
    tax = Tax(tax_id=f"tax_{i}", payment_id=payment.payment_id, type="GST", amount=tax_amt, created_at=created_at + timedelta(seconds=11))
    
    records.extend([order, payment, fee, tax])
    expected_settlement = amount - fee_amt - tax_amt
    
    items = []
    
    # Defaults for temporal
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
        
        # Omit linking the refund to the settlement item to force AI reasoning
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
        # Settlement created a long time ago, no bank tx
        initiated_at = created_at - timedelta(days=10)
        settlement = Settlement(settlement_id=f"set_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR{i}")
        items.append(SettlementItem(item_id=f"si_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        records.append(settlement)
        # Missing downstream
        
    elif scenario == "PENDING_BANK_SLA_SAFE":
        # Settlement just created, no bank tx yet
        initiated_at = datetime(2026, 8, 14, 10, 0, 0) # Just before evaluation
        settlement = Settlement(settlement_id=f"set_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR{i}")
        items.append(SettlementItem(item_id=f"si_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        records.append(settlement)

    elif scenario == "MISSING_FEE_EVIDENCE":
        # Settlement is missing the fee, but we hide the fee record from the system!
        # We simulate this by removing the fee from `records` and linking directly to bank
        records.remove(fee)
        settlement = Settlement(settlement_id=f"set_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR{i}")
        items.append(SettlementItem(item_id=f"si_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        bank_tx = BankTransaction(bank_transaction_id=f"btx_{i}", amount=expected_settlement, timestamp=initiated_at + timedelta(hours=2), reference=settlement.reference, direction="CREDIT")
        ledger = LedgerEntry(ledger_entry_id=f"led_{i}", bank_transaction_id=bank_tx.bank_transaction_id, account="SETTLEMENT_RECEIVABLE", amount=expected_settlement, type="CREDIT", timestamp=bank_tx.timestamp)
        records.extend([settlement, bank_tx, ledger])
        
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

def generate_dataset(num_orders: int = 2500, seed: int = 42) -> Tuple[List, List]:
    random.seed(seed)
    records = []
    cases = []
    base_time = datetime(2026, 8, 1, 10, 0, 0)
    
    for i in range(1, num_orders + 1):
        rand = random.random()
        if rand < 0.4:
            s = "CLEAN"
        elif rand < 0.5:
            s = "PARTIAL_REFUND"
        elif rand < 0.6:
            s = "SPLIT_SETTLEMENT"
        elif rand < 0.7:
            s = "DELAYED_SETTLEMENT_EXCEPTION"
        elif rand < 0.8:
            s = "PENDING_BANK_SLA_SAFE"
        elif rand < 0.9:
            s = "MISSING_FEE_EVIDENCE"
        else:
            s = "UNRESOLVABLE"
            
        r, c = generate_case(i, s, base_time)
        records.extend(r)
        cases.append((c["order_id"], c["ground_truth"]))
        
    return records, cases

def generate_demo_dataset() -> Tuple[List, List]:
    # Fixed 8 cases for Judge Demo
    scenarios = [
        "CLEAN",
        "PARTIAL_REFUND",
        "SPLIT_SETTLEMENT",
        "PENDING_BANK_SLA_SAFE",
        "DELAYED_SETTLEMENT_EXCEPTION",
        "MISSING_FEE_EVIDENCE",
        "UNRESOLVABLE"
    ]
    base_time = datetime(2026, 8, 1, 10, 0, 0)
    records = []
    cases = []
    for i, s in enumerate(scenarios, 1):
        r, c = generate_case(i * 1000, s, base_time)
        records.extend(r)
        cases.append((c["order_id"], c["ground_truth"]))
    return records, cases

if __name__ == "__main__":
    records, cases = generate_demo_dataset()
    print(f"Generated demo dataset with {len(records)} records for {len(cases)} cases.")

def generate_adversarial_case(i: int, scenario: str, base_time: datetime) -> Tuple[List, Dict]:
    records = []
    order_id = f"adv_{i}"
    
    amount = Decimal(random.randint(100, 50000))
    fee_amt = (amount * Decimal('0.02')).quantize(Decimal('0.01'))
    tax_amt = (fee_amt * Decimal('0.18')).quantize(Decimal('0.01'))
    created_at = base_time + timedelta(minutes=i*5)
    
    order = Order(order_id=order_id, customer_id=f"cust_adv_{i%100}", amount=amount, created_at=created_at, status="COMPLETED")
    payment = Payment(payment_id=f"pay_adv_{i}", order_id=order_id, amount=amount, captured_at=created_at + timedelta(seconds=10), status="CAPTURED", method="UPI")
    fee = Fee(fee_id=f"fee_adv_{i}", payment_id=payment.payment_id, type="GATEWAY", amount=fee_amt, created_at=created_at + timedelta(seconds=11))
    tax = Tax(tax_id=f"tax_adv_{i}", payment_id=payment.payment_id, type="GST", amount=tax_amt, created_at=created_at + timedelta(seconds=11))
    
    records.extend([order, payment, fee, tax])
    expected_settlement = amount - fee_amt - tax_amt
    initiated_at = created_at + timedelta(days=1)
    
    items = []
    
    if scenario == "ADV_SAME_AMOUNT_WRONG_TX":
        # Create correct settlement but missing bank tx
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        records.append(settlement)
        # Create an unrelated bank tx with SAME EXACT amount and close timestamp, but WRONG reference
        unrelated_btx = BankTransaction(bank_transaction_id=f"btx_adv_wrong_{i}", amount=expected_settlement, timestamp=initiated_at + timedelta(hours=2), reference=f"UTR_UNRELATED_{i}", direction="CREDIT")
        records.append(unrelated_btx)

    elif scenario == "ADV_WRONG_PERFECT_FEE":
        # Remove correct fee
        records.remove(fee)
        # Add fee with EXACT amount but wrong payment_id
        wrong_fee = Fee(fee_id=f"fee_adv_wrong_{i}", payment_id=f"pay_adv_other_{i}", type="GATEWAY", amount=fee_amt, created_at=created_at)
        records.append(wrong_fee)
        
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        bank_tx = BankTransaction(bank_transaction_id=f"btx_adv_{i}", amount=expected_settlement, timestamp=initiated_at + timedelta(hours=2), reference=settlement.reference, direction="CREDIT")
        records.extend([settlement, bank_tx])

    elif scenario == "ADV_DUPLICATE_UTR":
        # Two settlements with same reference, but only one is ours
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_dup_{i}")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        settlement2 = Settlement(settlement_id=f"set_adv_wrong_{i}", amount=expected_settlement+100, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_dup_{i}")
        bank_tx = BankTransaction(bank_transaction_id=f"btx_adv_{i}", amount=expected_settlement, timestamp=initiated_at + timedelta(hours=2), reference=f"UTR_adv_dup_{i}", direction="CREDIT")
        records.extend([settlement, settlement2, bank_tx])
        
    elif scenario == "ADV_DUPLICATE_PAYMENT":
        # Exact same payment ID with different amounts (Conflict)
        conflicting_payment = Payment(payment_id=payment.payment_id, order_id=order_id, amount=amount + Decimal('50.00'), captured_at=created_at + timedelta(seconds=12), status="CAPTURED", method="UPI")
        records.append(conflicting_payment)
        
    elif scenario == "ADV_MULTI_CURRENCY_LURE":
        # Settlement and payment are INR, bank tx is USD
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        bank_tx = BankTransaction(bank_transaction_id=f"btx_adv_{i}", amount=expected_settlement, currency="USD", timestamp=initiated_at, reference=settlement.reference, direction="CREDIT")
        records.extend([settlement, bank_tx])
        
    elif scenario == "ADV_TIMESTAMP_LURE":
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        bank_tx = BankTransaction(bank_transaction_id=f"btx_adv_{i}", amount=expected_settlement, timestamp=initiated_at + timedelta(days=2), reference=settlement.reference, direction="CREDIT")
        unrelated_btx = BankTransaction(bank_transaction_id=f"btx_adv_lure_{i}", amount=expected_settlement, timestamp=initiated_at + timedelta(minutes=5), reference="UNRELATED_UTR", direction="CREDIT")
        records.extend([settlement, bank_tx, unrelated_btx])
        
    elif scenario == "ADV_WRONG_REFUND_PERFECT_DISCREPANCY":
        # Create a settlement that is short by some amount, and a refund perfectly matching that amount but linked to another payment
        short_amount = expected_settlement - Decimal('50.00')
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=short_amount, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=short_amount))
        
        wrong_refund = Refund(refund_id=f"ref_adv_{i}", payment_id="pay_adv_OTHER", amount=Decimal('50.00'), status="PROCESSED", created_at=initiated_at)
        bank_tx = BankTransaction(bank_transaction_id=f"btx_adv_{i}", amount=short_amount, timestamp=initiated_at, reference=settlement.reference, direction="CREDIT")
        records.extend([settlement, bank_tx, wrong_refund])

    elif scenario == "ADV_MIXED_PROVENANCE_SPLIT":
        # Two settlement items sum perfectly, but one belongs to another payment
        part1 = expected_settlement // 2
        part2 = expected_settlement - part1
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}")
        items.extend([
            SettlementItem(item_id=f"si_adv_{i}_a", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=part1),
            SettlementItem(item_id=f"si_adv_{i}_b", settlement_id=settlement.settlement_id, payment_id="pay_adv_OTHER", amount=part2)
        ])
        bank_tx = BankTransaction(bank_transaction_id=f"btx_adv_{i}", amount=expected_settlement, timestamp=initiated_at, reference=settlement.reference, direction="CREDIT")
        records.extend([settlement, bank_tx])

    elif scenario == "ADV_DUPLICATE_BANK_IMPORT":
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        bank_tx1 = BankTransaction(bank_transaction_id=f"btx_adv_{i}", amount=expected_settlement, timestamp=initiated_at, reference=settlement.reference, direction="CREDIT")
        bank_tx2 = BankTransaction(bank_transaction_id=f"btx_adv_dup_{i}", amount=expected_settlement, timestamp=initiated_at, reference=settlement.reference, direction="CREDIT")
        records.extend([settlement, bank_tx1, bank_tx2])

    elif scenario == "ADV_WRONG_TAX_PERFECT_SIGNATURE":
        records.remove(tax)
        wrong_tax = Tax(tax_id=f"tax_adv_wrong_{i}", payment_id="pay_adv_OTHER", type="GST", amount=tax_amt, created_at=created_at)
        records.append(wrong_tax)
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        bank_tx = BankTransaction(bank_transaction_id=f"btx_adv_{i}", amount=expected_settlement, timestamp=initiated_at, reference=settlement.reference, direction="CREDIT")
        records.extend([settlement, bank_tx])

    elif scenario == "ADV_MANY_TO_MANY_COLLISION":
        settlement1 = Settlement(settlement_id=f"set_adv_{i}_a", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}_a")
        settlement2 = Settlement(settlement_id=f"set_adv_{i}_b", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}_b")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement1.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        items.append(SettlementItem(item_id=f"si_adv_{i}_2", settlement_id=settlement2.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        bank_tx = BankTransaction(bank_transaction_id=f"btx_adv_{i}", amount=expected_settlement, timestamp=initiated_at, reference=settlement1.reference, direction="CREDIT")
        records.extend([settlement1, settlement2, bank_tx])

    elif scenario == "ADV_CUSTOMER_COMPONENT_CONTAMINATION":
        # Share a customer ID with another order
        other_order_id = f"adv_other_{i}"
        other_order = Order(order_id=other_order_id, customer_id=order.customer_id, amount=Decimal('500.00'), status="COMPLETED", created_at=created_at)
        # It's in the records list, so it will get added to graph
        records.append(other_order)
        settlement = Settlement(settlement_id=f"set_adv_{i}", amount=expected_settlement, status="COMPLETED", initiated_at=initiated_at, reference=f"UTR_adv_{i}")
        items.append(SettlementItem(item_id=f"si_adv_{i}_1", settlement_id=settlement.settlement_id, payment_id=payment.payment_id, amount=expected_settlement))
        bank_tx = BankTransaction(bank_transaction_id=f"btx_adv_{i}", amount=expected_settlement, timestamp=initiated_at, reference=settlement.reference, direction="CREDIT")
        records.extend([settlement, bank_tx])

    else: # Fallback unresolvable
        pass

    records.extend(items)
    return records, {"order_id": order_id, "ground_truth": scenario}

def generate_adversarial_dataset() -> Tuple[List, List]:
    random.seed(99)
    records = []
    cases = []
    base_time = datetime(2026, 8, 5, 10, 0, 0)
    scenarios = [
        "ADV_SAME_AMOUNT_WRONG_TX",
        "ADV_WRONG_PERFECT_FEE",
        "ADV_DUPLICATE_UTR",
        "ADV_DUPLICATE_PAYMENT",
        "ADV_MULTI_CURRENCY_LURE",
        "ADV_TIMESTAMP_LURE",
        "ADV_WRONG_REFUND_PERFECT_DISCREPANCY",
        "ADV_MIXED_PROVENANCE_SPLIT",
        "ADV_DUPLICATE_BANK_IMPORT",
        "ADV_WRONG_TAX_PERFECT_SIGNATURE",
        "ADV_MANY_TO_MANY_COLLISION",
        "ADV_CUSTOMER_COMPONENT_CONTAMINATION"
    ] * 3 # 36 cases total
    
    for i, s in enumerate(scenarios, 1):
        r, c = generate_adversarial_case(i, s, base_time)
        records.extend(r)
        cases.append((c["order_id"], c["ground_truth"]))
        
    return records, cases
