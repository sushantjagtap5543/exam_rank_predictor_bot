"""
Cashfree Payment Gateway Integration (Orders API v2023-08-01)
=============================================================
Provides production-grade order creation, order status re-fetching,
and HMAC-SHA256 webhook signature verification for ExamRankers store & VIP channel.
"""

import os
import hmac
import base64
import hashlib
import time
import logging
from typing import Dict, Any, Optional, Tuple
import httpx

logger = logging.getLogger(__name__)

CASHFREE_API_VERSION = "2023-08-01"
SANDBOX_BASE_URL = "https://sandbox.cashfree.com/pg"
PRODUCTION_BASE_URL = "https://api.cashfree.com/pg"

class CashfreeClient:
    """Official Cashfree Payment Gateway Client for Orders API."""

    def __init__(
        self,
        app_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        env: Optional[str] = None
    ):
        self.app_id = (app_id or os.getenv("CASHFREE_APP_ID", "")).strip()
        self.secret_key = (secret_key or os.getenv("CASHFREE_SECRET_KEY", "")).strip()
        self.env = (env or os.getenv("CASHFREE_ENV", "TEST")).strip().upper()
        self.base_url = PRODUCTION_BASE_URL if self.env in ("PROD", "PRODUCTION") else SANDBOX_BASE_URL

    @property
    def is_configured(self) -> bool:
        """Returns True if valid App ID and Secret Key are configured."""
        return bool(self.app_id and self.secret_key and not self.app_id.startswith("your_"))

    def _get_headers(self) -> Dict[str, str]:
        return {
            "x-client-id": self.app_id,
            "x-client-secret": self.secret_key,
            "x-api-version": CASHFREE_API_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def create_order(
        self,
        order_id: str,
        amount: float,
        customer_email: str,
        customer_phone: str = "9999999999",
        customer_id: Optional[str] = None,
        return_url: Optional[str] = None,
        notify_url: Optional[str] = None,
        order_note: str = "ExamRankers Digital E-Book"
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Creates an order on Cashfree PG and returns (success, response_dict).
        Response contains payment_session_id and cf_order_id.
        """
        if not self.is_configured:
            # Mock sandbox mode when credentials not configured (for offline testing)
            mock_session = f"session_mock_{hashlib.sha256(order_id.encode()).hexdigest()[:24]}"
            return True, {
                "order_id": order_id,
                "cf_order_id": f"cf_{order_id}",
                "payment_session_id": mock_session,
                "order_status": "ACTIVE",
                "is_mock": True
            }

        cust_id = customer_id or f"cust_{hashlib.sha256(customer_email.lower().encode()).hexdigest()[:16]}"
        payload = {
            "order_id": order_id,
            "order_amount": round(float(amount), 2),
            "order_currency": "INR",
            "customer_details": {
                "customer_id": cust_id,
                "customer_email": customer_email.strip().lower(),
                "customer_phone": re_clean_phone(customer_phone)
            },
            "order_meta": {
                "return_url": return_url or f"/order/{order_id}?order_id={order_id}",
                "notify_url": notify_url or os.getenv("CASHFREE_WEBHOOK_URL", "")
            },
            "order_note": order_note[:100]
        }

        url = f"{self.base_url}/orders"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload, headers=self._get_headers())
                data = resp.json()
                if resp.status_code in (200, 201):
                    return True, data
                logger.error(f"Cashfree create_order failed [{resp.status_code}]: {data}")
                return False, {"error": data.get("message", "Order creation failed"), "details": data}
        except Exception as e:
            logger.error(f"Cashfree create_order network exception: {e}")
            return False, {"error": str(e)}

    async def get_order(self, order_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Fetches official order details directly from Cashfree API.
        Used to verify true payment status server-to-server.
        """
        if not self.is_configured:
            return False, {"error": "Cashfree credentials not configured"}

        url = f"{self.base_url}/orders/{order_id}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=self._get_headers())
                data = resp.json()
                if resp.status_code == 200:
                    return True, data
                logger.warning(f"Cashfree get_order failed [{resp.status_code}]: {data}")
                return False, data
        except Exception as e:
            logger.error(f"Cashfree get_order exception for {order_id}: {e}")
            return False, {"error": str(e)}

    def verify_webhook_signature(
        self,
        raw_body: bytes,
        timestamp: str,
        signature: str,
        max_drift_seconds: int = 300
    ) -> bool:
        """
        Verifies Cashfree webhook signature using HMAC-SHA256.
        Formula: Base64(HMAC-SHA256(timestamp + raw_body, secret_key))
        Enforces constant-time comparison and rejects stale timestamps.
        """
        if not self.secret_key or not timestamp or not signature:
            return False

        # Replay attack prevention: check timestamp drift
        try:
            ts_float = float(timestamp)
            # Cashfree timestamps can be in milliseconds or seconds
            if ts_float > 1e11:
                ts_float = ts_float / 1000.0
            current_ts = time.time()
            if abs(current_ts - ts_float) > max_drift_seconds:
                logger.warning(f"Rejected stale Cashfree webhook (drift: {abs(current_ts - ts_float):.1f}s)")
                return False
        except (ValueError, TypeError):
            logger.warning(f"Invalid Cashfree webhook timestamp: {timestamp}")
            return False

        # Construct signed payload: timestamp bytes + raw body bytes
        try:
            payload = timestamp.encode("utf-8") + raw_body
            computed_hmac = hmac.new(self.secret_key.encode("utf-8"), payload, hashlib.sha256).digest()
            computed_sig = base64.b64encode(computed_hmac).decode("utf-8")
            return hmac.compare_digest(computed_sig, signature.strip())
        except Exception as e:
            logger.error(f"Error computing Cashfree signature: {e}")
            return False

def re_clean_phone(phone: str) -> str:
    """Ensures phone number has exactly 10 digits as required by Cashfree."""
    import re
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) >= 10:
        return digits[-10:]
    return "9999999999"

