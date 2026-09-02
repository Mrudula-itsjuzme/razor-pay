import json
from decimal import Decimal
import datetime
from datagen import generate_demo_dataset, generate_adversarial_dataset, generate_complex_dataset
from graph import ProvenanceGraph
from main import engine, evaluate_system
from eval_engine import calculate_proof_debt, safe_automation_frontier, evidence_degradation_experiment

def make_graph(records):
    g = ProvenanceGraph()
    for rec in records:
        t = type(rec).__name__
        if t == "Order": g.add_order(rec)
        elif t == "Payment": g.add_payment(rec)
        elif t == "Refund": g.add_refund(rec)
        elif t == "Fee": g.add_fee(rec)
        elif t == "Tax": g.add_tax(rec)
        elif t == "BankTransaction": g.add_bank_transaction(rec)
    
    for rec in records:
        if type(rec).__name__ == "Settlement":
            items = [r for r in records if type(r).__name__ == "SettlementItem" and r.settlement_id == rec.settlement_id]
            g.add_settlement(rec, items)
            
    for n, data in g.g.nodes(data=True):
        if data.get('type') == 'BankTransaction':
            tx = data['data']
            if tx.reference:
                for sn, sdata in g.g.nodes(data=True):
                    if sdata.get('type') == 'Settlement' and sdata['data'].reference == tx.reference:
                        g.link_bank_transaction_to_settlement(tx.bank_transaction_id, sdata['data'].settlement_id)
    return g

def main():
    with open('final_evaluation.json', 'r') as f:
        data = json.load(f)
        
    md = f"""# Final Evaluation Results

Generated at: {data['timestamp']}

## Datasets
- **NORMAL_HELD_OUT**: {data['datasets']['NORMAL_HELD_OUT']['cases']} cases, {data['datasets']['NORMAL_HELD_OUT']['records']} records
- **ADVERSARIAL**: {data['datasets']['ADVERSARIAL']['cases']} cases, {data['datasets']['ADVERSARIAL']['records']} records
- **COMPLEX_FINANCE_CLOSE**: {data['datasets']['COMPLEX_FINANCE_CLOSE']['cases']} cases, {data['datasets']['COMPLEX_FINANCE_CLOSE']['records']} records (Value: ₹{data['datasets']['COMPLEX_FINANCE_CLOSE']['value']:.2f})

## Complex Finance Close Benchmark
| Metric | Exact | Rules | Controller |
|--------|-------|-------|------------|
| Decision F1 | {data['COMPLEX_FINANCE_CLOSE_BENCHMARK']['exact']['f1']:.4f} | {data['COMPLEX_FINANCE_CLOSE_BENCHMARK']['rules']['f1']:.4f} | {data['COMPLEX_FINANCE_CLOSE_BENCHMARK']['controller']['f1']:.4f} |
| Safe Auto-closure | {data['COMPLEX_FINANCE_CLOSE_BENCHMARK']['exact']['correct_abstention_rate']:.4f} | {data['COMPLEX_FINANCE_CLOSE_BENCHMARK']['rules']['correct_abstention_rate']:.4f} | {data['COMPLEX_FINANCE_CLOSE_BENCHMARK']['controller']['correct_abstention_rate']:.4f} |
| Unsafe Closure | {data['COMPLEX_FINANCE_CLOSE_BENCHMARK']['exact']['unsafe_closure_rate']:.4f} | {data['COMPLEX_FINANCE_CLOSE_BENCHMARK']['rules']['unsafe_closure_rate']:.4f} | {data['COMPLEX_FINANCE_CLOSE_BENCHMARK']['controller']['unsafe_closure_rate']:.4f} |

## Close The Books Workflow
- **Batch Size**: {data['CLOSE_THE_BOOKS']['batch_size']} cases
- **Value**: ₹{data['CLOSE_THE_BOOKS']['value']:.2f}
- **Proven Value**: ₹{data['CLOSE_THE_BOOKS']['proven_value']:.2f}
- **Proof Debt**: ₹{data['CLOSE_THE_BOOKS']['proof_debt']['total']:.2f}
- **Exceptions**: {data['CLOSE_THE_BOOKS']['exceptions']}
- **Automation Rate**: {data['CLOSE_THE_BOOKS']['automation_rate'] * 100:.1f}%
"""
    with open('final_evaluation.md', 'w') as f:
        f.write(md)

if __name__ == "__main__":
    main()
