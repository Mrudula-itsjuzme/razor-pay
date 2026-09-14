import json
from datetime import datetime, timedelta
from decimal import Decimal
from models import *
from graph import ProvenanceGraph
from reconciliation import ReconciliationEngine

def scenario(kind):
    dt = datetime(2026, 8, 1)
    g = ProvenanceGraph()
    g.add_order(Order(order_id='o', customer_id='c', amount='100', status='COMPLETED', created_at=dt))
    g.add_payment(Payment(payment_id='p', order_id='o', amount='100', status='CAPTURED', method='UPI', captured_at=dt))
    net = '99' if kind in ['tax_currency','future_tax','future_refund'] else '100'
    if kind in ['tax_currency','future_tax']:
        g.add_tax(Tax(tax_id='t', payment_id='p', type='GST', amount='1', currency='USD' if kind=='tax_currency' else 'INR', created_at=dt+timedelta(days=100) if kind=='future_tax' else dt))
    if kind=='future_refund':
        g.add_refund(Refund(refund_id='r', payment_id='p', amount='1', status='PROCESSED', created_at=dt+timedelta(days=100)))
    g.add_settlement(Settlement(settlement_id='s',amount=net,status='FAILED' if kind=='failed_settlement' else 'COMPLETED', initiated_at=dt,reference='utr'),[SettlementItem(item_id='i',settlement_id='s',payment_id='p',amount='100' if kind=='future_refund' else net)])
    g.add_bank_transaction(BankTransaction(bank_transaction_id='b',amount=net,timestamp=dt,reference='utr',direction='DEBIT' if kind=='bank_debit' else 'CREDIT'))
    g.link_bank_transaction_to_settlement('b','s')
    if kind=='order_amount':
        g.g.nodes['order_o']['data'].amount=Decimal('1000')
    res=ReconciliationEngine().reconcile_order(g.get_subgraph_for_order('o'),target_order_id='o',as_of_time=dt+timedelta(days=5))
    return {k:res[k] for k in ['decision','proof_validity','expected_net']}

out={k:scenario(k) for k in ['control','bank_debit','failed_settlement','tax_currency','future_tax','future_refund','order_amount']}
from fastapi.testclient import TestClient
import main
from unittest.mock import patch
c=TestClient(main.app,raise_server_exceptions=False)
out['unauth_demo_status']=c.post('/api/demo').status_code
oid=next(o for o,s in main.global_cases if s=='CLEAN')
out['timezone_query_status']=c.get('/api/reconcile/'+oid,params={'as_of_time':'2026-09-06T12:00:00Z'}).status_code
c.post('/api/degrade/'+oid)
out['degraded_detail']=c.get('/api/reconcile/'+oid).json()['decision']
out['degraded_list']=next(x['decision'] for x in c.get('/api/cases').json() if x['order_id']==oid)
c.post('/api/demo')
out['degrade_survives_reload']=oid in main.degraded_orders
with patch.object(main.RazorpayAdapter,'fetch_recent_data',return_value=([], 'offline test')):
    r=c.post('/api/ingest',params={'num_orders':-1})
    out['negative_ingest']={'status':r.status_code,'remaining_cases':len(main.global_cases)}
print(json.dumps(out,indent=2))
