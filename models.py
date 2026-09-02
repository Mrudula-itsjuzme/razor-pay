from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime
from typing import Optional, Literal

class BaseRecord(BaseModel):
    pass

class Order(BaseRecord):
    order_id: str
    customer_id: str
    amount: Decimal
    currency: str = "INR"
    created_at: datetime
    status: str

class Payment(BaseRecord):
    payment_id: str
    order_id: str
    amount: Decimal
    currency: str = "INR"
    captured_at: datetime
    status: str
    method: str

class Refund(BaseRecord):
    refund_id: str
    payment_id: str
    amount: Decimal
    currency: str = "INR"
    created_at: datetime
    status: str

class Fee(BaseRecord):
    fee_id: str
    payment_id: Optional[str] = None
    settlement_id: Optional[str] = None
    type: str
    amount: Decimal
    currency: str = "INR"
    created_at: datetime

class Tax(BaseRecord):
    tax_id: str
    payment_id: Optional[str] = None
    settlement_id: Optional[str] = None
    type: str
    amount: Decimal
    currency: str = "INR"
    created_at: datetime

class Settlement(BaseRecord):
    settlement_id: str
    amount: Decimal
    currency: str = "INR"
    status: str
    initiated_at: datetime
    completed_at: Optional[datetime] = None
    reference: Optional[str] = None

class BankTransaction(BaseRecord):
    bank_transaction_id: str
    amount: Decimal
    currency: str = "INR"
    timestamp: datetime
    reference: Optional[str] = None
    direction: Literal["CREDIT", "DEBIT"]

class LedgerEntry(BaseRecord):
    ledger_entry_id: str
    amount: Decimal
    currency: str = "INR"
    timestamp: datetime
    account: str
    type: Literal["CREDIT", "DEBIT"]
    reference: Optional[str] = None

class SettlementItem(BaseRecord):
    # Relates a payment or refund to a settlement explicitly
    item_id: str
    settlement_id: str
    payment_id: Optional[str] = None
    refund_id: Optional[str] = None
    amount: Decimal  # Positive for payment, negative for refund/fee
    currency: str = "INR"
