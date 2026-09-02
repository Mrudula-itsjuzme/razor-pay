import os
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Any, Tuple
from models import Order, Payment, Refund, Fee, Tax, Settlement, BankTransaction, SettlementItem

class RazorpayAdapter:
    def __init__(self, key_id: str = None, key_secret: str = None):
        self.key_id = key_id or os.getenv("RAZORPAY_KEY_ID")
        self.key_secret = key_secret or os.getenv("RAZORPAY_KEY_SECRET")
        self.client = None
        self.is_live = False
        
        if self.key_id and self.key_secret:
            try:
                import razorpay
                self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
                self.is_live = True
            except ImportError:
                print("razorpay package not installed. Operating in offline/mock mode.")

    def fetch_recent_data(self) -> Tuple[List[Any], Dict[str, str]]:
        """
        Fetches live data from Razorpay if credentials are provided.
        Returns a tuple of (canonical_records, status_message).
        """
        if not self.is_live:
            return [], "Razorpay mode: adapter ready, live credentials unavailable. Please use synthetic ingestion."
            
        records = []
        try:
            # Pseudo-implementation mapping Razorpay entities to canonical models
            orders = self.client.order.fetch_all()
            for rzp_order in orders['items']:
                order = Order(
                    order_id=rzp_order['id'],
                    customer_id=rzp_order.get('customer_id', 'unknown'),
                    amount=Decimal(rzp_order['amount']) / 100, # RZP uses paisa
                    created_at=datetime.fromtimestamp(rzp_order['created_at']),
                    status=rzp_order['status']
                )
                records.append(order)
                
            # ... fetch payments, refunds, settlements, map them similarly.
            return records, "Successfully fetched and mapped live Razorpay data."
            
        except Exception as e:
            return [], f"Failed to fetch live data: {str(e)}"
