# backend/payments/services.py
import requests
import json
import logging
import uuid
import hmac
import hashlib
from decimal import Decimal
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

FLUTTERWAVE_BASE_URL = "https://api.flutterwave.com/v3"

class FlutterwaveService:
    @staticmethod
    def get_headers():
        return {
            "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
            "Content-Type": "application/json",
        }

    @classmethod
    def is_live_configured(cls):
        key = getattr(settings, 'FLUTTERWAVE_SECRET_KEY', '')
        return bool(key and not key.startswith('FLWSECK_TEST-SANDBOX') and 'DEMO' not in key)

    @classmethod
    def initialize_payment(cls, tx_ref, amount, currency, customer_email, customer_name, redirect_url, title, description, meta=None):
        """
        Initiates a payment with Flutterwave standard checkout.
        """
        payload = {
            "tx_ref": tx_ref,
            "amount": str(amount),
            "currency": currency or "NGN",
            "redirect_url": redirect_url,
            "customer": {
                "email": customer_email,
                "name": customer_name or "Anonymous Supporter",
            },
            "customizations": {
                "title": title,
                "description": description,
                "logo": f"{settings.FRONTEND_URL}/logo.png",
            },
            "meta": meta or {},
        }

        # If live Flutterwave secret key is configured, call Flutterwave API
        if cls.is_live_configured():
            try:
                response = requests.post(
                    f"{FLUTTERWAVE_BASE_URL}/payments",
                    headers=cls.get_headers(),
                    json=payload,
                    timeout=20
                )
                res_data = response.json()
                if response.status_code == 200 and res_data.get('status') == 'success':
                    return {
                        "success": True,
                        "payment_link": res_data['data']['link'],
                        "tx_ref": tx_ref,
                        "data": res_data['data']
                    }
                else:
                    logger.error(f"Flutterwave init payment failed: {res_data}")
                    return {
                        "success": False,
                        "error": res_data.get('message', 'Failed to initialize payment')
                    }
            except Exception as e:
                logger.exception("Flutterwave payment initialization exception")
                return {"success": False, "error": str(e)}

        # Fallback Sandbox / Dev Mode URL for immediate testing & demo
        dev_payment_link = f"{settings.FRONTEND_URL}/payment/process?tx_ref={tx_ref}&amount={amount}&currency={currency}"
        return {
            "success": True,
            "payment_link": dev_payment_link,
            "tx_ref": tx_ref,
            "is_sandbox": True,
            "data": {
                "link": dev_payment_link,
                "tx_ref": tx_ref,
                "amount": amount,
                "currency": currency
            }
        }

    @classmethod
    def verify_transaction(cls, transaction_id=None, tx_ref=None):
        """
        Verifies transaction status directly with Flutterwave.
        """
        if cls.is_live_configured() and transaction_id:
            try:
                response = requests.get(
                    f"{FLUTTERWAVE_BASE_URL}/transactions/{transaction_id}/verify",
                    headers=cls.get_headers(),
                    timeout=20
                )
                res_data = response.json()
                if response.status_code == 200 and res_data.get('status') == 'success':
                    data = res_data['data']
                    return {
                        "success": data.get('status') == 'successful',
                        "status": data.get('status'),
                        "amount": Decimal(str(data.get('amount', 0))),
                        "currency": data.get('currency'),
                        "tx_ref": data.get('tx_ref'),
                        "flw_ref": data.get('flw_ref'),
                        "customer": data.get('customer', {}),
                        "raw_data": data
                    }
                return {
                    "success": False,
                    "status": "failed",
                    "error": res_data.get('message', 'Verification failed')
                }
            except Exception as e:
                logger.exception("Flutterwave verify transaction exception")
                return {"success": False, "status": "failed", "error": str(e)}

        # Sandbox / Dev mode fallback verification
        return {
            "success": True,
            "status": "successful",
            "tx_ref": tx_ref,
            "flw_ref": f"FLW_MOCK_{uuid.uuid4().hex[:10].upper()}",
            "is_sandbox": True
        }

    @classmethod
    def verify_webhook_signature(cls, request):
        secret_hash = getattr(settings, 'FLUTTERWAVE_SECRET_HASH', '')
        if not secret_hash:
            return True
        signature = request.headers.get('verif-hash', '')
        return signature == secret_hash

    @classmethod
    def get_supported_banks(cls, country="NG"):
        """
        Fetches list of banks for payouts.
        """
        if cls.is_live_configured():
            try:
                response = requests.get(
                    f"{FLUTTERWAVE_BASE_URL}/banks/{country}",
                    headers=cls.get_headers(),
                    timeout=15
                )
                if response.status_code == 200:
                    return response.json().get('data', [])
            except Exception as e:
                logger.error(f"Error fetching banks: {e}")

        # Standard Nigerian & African Banks preset fallback
        return [
            {"id": 1, "code": "044", "name": "Access Bank"},
            {"id": 2, "code": "023", "name": "Citibank Nigeria"},
            {"id": 3, "code": "050", "name": "Ecobank Nigeria"},
            {"id": 4, "code": "070", "name": "Fidelity Bank"},
            {"id": 5, "code": "011", "name": "First Bank of Nigeria"},
            {"id": 6, "code": "214", "name": "First City Monument Bank (FCMB)"},
            {"id": 7, "code": "058", "name": "Guaranty Trust Bank (GTBank)"},
            {"id": 8, "code": "030", "name": "Heritage Bank"},
            {"id": 9, "code": "301", "name": "Jaiz Bank"},
            {"id": 10, "code": "082", "name": "Keystone Bank"},
            {"id": 11, "code": "999992", "name": "OPay"},
            {"id": 12, "code": "999991", "name": "PalmPay"},
            {"id": 13, "code": "076", "name": "Polaris Bank"},
            {"id": 14, "code": "101", "name": "Providus Bank"},
            {"id": 15, "code": "221", "name": "Stanbic IBTC Bank"},
            {"id": 16, "code": "068", "name": "Standard Chartered Bank"},
            {"id": 17, "code": "232", "name": "Sterling Bank"},
            {"id": 18, "code": "100", "name": "Suntrust Bank"},
            {"id": 19, "code": "032", "name": "Union Bank of Nigeria"},
            {"id": 20, "code": "033", "name": "United Bank for Africa (UBA)"},
            {"id": 21, "code": "215", "name": "Unity Bank"},
            {"id": 22, "code": "035", "name": "Wema Bank (ALAT)"},
            {"id": 23, "code": "057", "name": "Zenith Bank"},
            {"id": 24, "code": "50211", "name": "Kuda Microfinance Bank"},
            {"id": 25, "code": "51253", "name": "Moniepoint MFB"},
        ]

    @classmethod
    def resolve_account_number(cls, account_number, bank_code):
        """
        Validates account number and retrieves account holder name.
        """
        if cls.is_live_configured():
            try:
                response = requests.post(
                    f"{FLUTTERWAVE_BASE_URL}/accounts/resolve",
                    headers=cls.get_headers(),
                    json={"account_number": account_number, "account_bank": bank_code},
                    timeout=15
                )
                res_data = response.json()
                if response.status_code == 200 and res_data.get('status') == 'success':
                    return {
                        "success": True,
                        "account_name": res_data['data']['account_name'],
                        "account_number": res_data['data']['account_number'],
                    }
                return {"success": False, "error": res_data.get('message', 'Account verification failed')}
            except Exception as e:
                logger.error(f"Error resolving account: {e}")
                return {"success": False, "error": str(e)}

        # Sandbox account resolver mock
        return {
            "success": True,
            "account_name": "Verified Creator Account",
            "account_number": account_number,
        }
