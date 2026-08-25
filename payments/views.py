# backend/payments/views.py
import uuid
import secrets
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.db import transaction as db_transaction
from django.conf import settings
from rest_framework import generics, status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from accounts.models import User
from anonymous_messages.models import QASession, AnonymousMessage
from .models import Wallet, PaymentTransaction, Gift, QASessionAccess, PayoutRequest
from .serializers import (
    WalletSerializer,
    PaymentTransactionSerializer,
    GiftSerializer,
    InitializeGiftSerializer,
    InitializeQAPassSerializer,
    VerifyPaymentSerializer,
    PayoutRequestSerializer,
    QASessionAccessSerializer
)
from .services import FlutterwaveService

# Platform Revenue Fee (7.5% per donation / paid pass)
PLATFORM_FEE_PERCENT = Decimal('7.5')


def calculate_platform_fees(gross_amount):
    """
    Calculates platform service fee and net creator settlement.
    Example: ₦1,000 gross -> ₦75 platform fee, ₦925 net creator payout
    """
    gross = Decimal(str(gross_amount))
    fee = round(gross * (PLATFORM_FEE_PERCENT / Decimal('100.0')), 2)
    net = gross - fee
    return fee, net


def calculate_gift_badge(amount):
    val = float(amount)
    if val >= 50000:
        return 'Diamond Legend'
    elif val >= 20000:
        return 'Angel Backer'
    elif val >= 5000:
        return 'Gold Champion'
    elif val >= 2000:
        return 'Silver VIP'
    return 'Bronze Supporter'


class InitializeGiftPaymentView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = InitializeGiftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        creator_user = get_object_or_404(User, username=data['creator_username'])
        amount = data['amount']
        currency = data.get('currency', 'NGN')
        tx_ref = f"GIFT-{uuid.uuid4().hex[:12].upper()}"

        payer_email = data.get('payer_email') or f"supporter_{uuid.uuid4().hex[:6]}@anonymsg.com"
        payer_name = data.get('sender_alias') or "Generous Anon"
        redirect_url = data.get('redirect_url') or f"{settings.FRONTEND_URL}/{creator_user.username}?payment=gift_success&tx_ref={tx_ref}"

        pmt_tx = PaymentTransaction.objects.create(
            tx_ref=tx_ref,
            transaction_type='gift',
            amount=amount,
            currency=currency,
            status='pending',
            creator=creator_user,
            payer_email=payer_email,
            payer_name=payer_name,
            is_anonymous=data.get('is_anonymous', True),
            donor_alias=data.get('sender_alias', 'Generous Anon'),
            gift_note=data.get('message', ''),
            meta_data={
                "creator": creator_user.username,
                "type": "gift",
                "note": data.get('message', '')
            }
        )

        title = f"Gift for @{creator_user.username}"
        description = f"Send a {currency} {amount:,.2f} creator tip on AnonMsg"

        fw_res = FlutterwaveService.initialize_payment(
            tx_ref=tx_ref,
            amount=amount,
            currency=currency,
            customer_email=payer_email,
            customer_name=payer_name,
            redirect_url=redirect_url,
            title=title,
            description=description,
            meta={"tx_ref": tx_ref, "creator_id": str(creator_user.id)}
        )

        if fw_res.get('success'):
            return Response({
                "success": True,
                "payment_link": fw_res.get('payment_link'),
                "tx_ref": tx_ref,
                "amount": str(amount),
                "currency": currency,
                "creator_username": creator_user.username,
                "is_sandbox": fw_res.get('is_sandbox', False)
            }, status=status.HTTP_200_OK)
        else:
            pmt_tx.status = 'failed'
            pmt_tx.save()
            return Response({"success": False, "error": fw_res.get('error')}, status=status.HTTP_400_BAD_REQUEST)


class InitializeQAPassPaymentView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = InitializeQAPassSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        qa_session = get_object_or_404(QASession, id=data['session_id'])
        email = data['email'].strip().lower()
        name = data.get('name', 'Attendee')

        # If session is free, generate access pass directly
        if not qa_session.is_paid or qa_session.price <= 0:
            token = f"FREE-{uuid.uuid4().hex}"
            access, _ = QASessionAccess.objects.get_or_create(
                session=qa_session,
                email=email,
                defaults={"name": name, "access_token": token}
            )
            return Response({
                "success": True,
                "is_free": True,
                "access_token": access.access_token,
                "message": "Free access pass granted"
            }, status=status.HTTP_200_OK)

        # Paid session checkout
        tx_ref = f"QAPASS-{uuid.uuid4().hex[:12].upper()}"
        redirect_url = data.get('redirect_url') or f"{settings.FRONTEND_URL}/qa/{qa_session.id}?unlocked=true&tx_ref={tx_ref}"

        pmt_tx = PaymentTransaction.objects.create(
            tx_ref=tx_ref,
            transaction_type='paid_qa_access',
            amount=qa_session.price,
            currency=qa_session.currency,
            status='pending',
            creator=qa_session.host,
            payer_email=email,
            payer_name=name,
            qa_session=qa_session,
            meta_data={
                "session_id": str(qa_session.id),
                "session_title": qa_session.title,
                "email": email,
                "name": name
            }
        )

        title = f"VIP Access: {qa_session.title[:30]}"
        description = f"Exclusive access ticket to Live Q&A by @{qa_session.host.username}"

        fw_res = FlutterwaveService.initialize_payment(
            tx_ref=tx_ref,
            amount=qa_session.price,
            currency=qa_session.currency,
            customer_email=email,
            customer_name=name,
            redirect_url=redirect_url,
            title=title,
            description=description,
            meta={"tx_ref": tx_ref, "session_id": str(qa_session.id)}
        )

        if fw_res.get('success'):
            return Response({
                "success": True,
                "is_free": False,
                "payment_link": fw_res.get('payment_link'),
                "tx_ref": tx_ref,
                "amount": str(qa_session.price),
                "currency": qa_session.currency,
                "is_sandbox": fw_res.get('is_sandbox', False)
            }, status=status.HTTP_200_OK)
        else:
            pmt_tx.status = 'failed'
            pmt_tx.save()
            return Response({"success": False, "error": fw_res.get('error')}, status=status.HTTP_400_BAD_REQUEST)


class VerifyPaymentView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tx_ref = serializer.validated_data['tx_ref']
        transaction_id = serializer.validated_data.get('transaction_id')

        pmt_tx = get_object_or_404(PaymentTransaction, tx_ref=tx_ref)

        if pmt_tx.status == 'successful':
            # Already completed
            access_token = None
            if pmt_tx.transaction_type == 'paid_qa_access' and pmt_tx.qa_session:
                access = QASessionAccess.objects.filter(session=pmt_tx.qa_session, email=pmt_tx.payer_email).first()
                if access:
                    access_token = access.access_token

            return Response({
                "success": True,
                "message": "Payment already verified",
                "transaction": PaymentTransactionSerializer(pmt_tx).data,
                "access_token": access_token
            }, status=status.HTTP_200_OK)

        verify_res = FlutterwaveService.verify_transaction(
            transaction_id=transaction_id,
            tx_ref=tx_ref
        )

        if verify_res.get('success'):
            with db_transaction.atomic():
                gross_amt = Decimal(str(pmt_tx.amount))
                platform_fee, net_creator_amt = calculate_platform_fees(gross_amt)

                pmt_tx.status = 'successful'
                pmt_tx.flw_ref = verify_res.get('flw_ref', '')
                pmt_tx.flw_transaction_id = str(transaction_id or '')
                
                # Record financial audit metadata
                tx_meta = pmt_tx.meta_data or {}
                tx_meta.update({
                    "gross_amount": str(gross_amt),
                    "platform_fee": str(platform_fee),
                    "net_creator_amount": str(net_creator_amt),
                    "fee_percentage": f"{PLATFORM_FEE_PERCENT}%"
                })
                pmt_tx.meta_data = tx_meta
                pmt_tx.save()

                # Credit Net Creator Amount to Creator Wallet
                creator_wallet, _ = Wallet.objects.get_or_create(user=pmt_tx.creator)
                creator_wallet.balance += net_creator_amt
                creator_wallet.total_earned += net_creator_amt
                creator_wallet.save()

                access_token = None

                # Handle Gift
                if pmt_tx.transaction_type == 'gift':
                    badge = calculate_gift_badge(pmt_tx.amount)
                    Gift.objects.get_or_create(
                        transaction=pmt_tx,
                        defaults={
                            "creator": pmt_tx.creator,
                            "amount": pmt_tx.amount,
                            "currency": pmt_tx.currency,
                            "sender_alias": pmt_tx.donor_alias or 'Generous Anon',
                            "is_anonymous": pmt_tx.is_anonymous,
                            "message": pmt_tx.gift_note or '',
                            "badge": badge
                        }
                    )

                # Handle Paid Q&A Access Pass
                elif pmt_tx.transaction_type == 'paid_qa_access' and pmt_tx.qa_session:
                    qa = pmt_tx.qa_session
                    qa.total_revenue += net_creator_amt
                    qa.save()

                    token = f"PASS-{uuid.uuid4().hex}"
                    access_record, _ = QASessionAccess.objects.get_or_create(
                        session=qa,
                        email=pmt_tx.payer_email,
                        defaults={
                            "name": pmt_tx.payer_name or 'Pass Holder',
                            "access_token": token,
                            "transaction": pmt_tx
                        }
                    )
                    access_token = access_record.access_token

            return Response({
                "success": True,
                "message": "Payment verified successfully!",
                "transaction": PaymentTransactionSerializer(pmt_tx).data,
                "access_token": access_token
            }, status=status.HTTP_200_OK)
        else:
            pmt_tx.status = 'failed'
            pmt_tx.save()
            return Response({
                "success": False,
                "error": verify_res.get('error', 'Payment verification failed')
            }, status=status.HTTP_400_BAD_REQUEST)


class FlutterwaveWebhookView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not FlutterwaveService.verify_webhook_signature(request):
            return Response({"error": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED)

        event = request.data
        data = event.get('data', {})
        tx_ref = data.get('tx_ref')
        status_val = data.get('status')

        if not tx_ref:
            return Response({"status": "ignored"}, status=status.HTTP_200_OK)

        try:
            pmt_tx = PaymentTransaction.objects.get(tx_ref=tx_ref)
            if status_val == 'successful' and pmt_tx.status != 'successful':
                with db_transaction.atomic():
                    gross_amt = Decimal(str(pmt_tx.amount))
                    platform_fee, net_creator_amt = calculate_platform_fees(gross_amt)

                    pmt_tx.status = 'successful'
                    pmt_tx.flw_ref = data.get('flw_ref', '')
                    pmt_tx.flw_transaction_id = str(data.get('id', ''))

                    tx_meta = pmt_tx.meta_data or {}
                    tx_meta.update({
                        "gross_amount": str(gross_amt),
                        "platform_fee": str(platform_fee),
                        "net_creator_amount": str(net_creator_amt),
                        "fee_percentage": f"{PLATFORM_FEE_PERCENT}%"
                    })
                    pmt_tx.meta_data = tx_meta
                    pmt_tx.save()

                    creator_wallet, _ = Wallet.objects.get_or_create(user=pmt_tx.creator)
                    creator_wallet.balance += net_creator_amt
                    creator_wallet.total_earned += net_creator_amt
                    creator_wallet.save()

                    if pmt_tx.transaction_type == 'gift':
                        Gift.objects.get_or_create(
                            transaction=pmt_tx,
                            defaults={
                                "creator": pmt_tx.creator,
                                "amount": pmt_tx.amount,
                                "currency": pmt_tx.currency,
                                "sender_alias": pmt_tx.donor_alias or 'Generous Anon',
                                "is_anonymous": pmt_tx.is_anonymous,
                                "message": pmt_tx.gift_note or '',
                                "badge": calculate_gift_badge(pmt_tx.amount)
                            }
                        )
                    elif pmt_tx.transaction_type == 'paid_qa_access' and pmt_tx.qa_session:
                        qa = pmt_tx.qa_session
                        qa.total_revenue += net_creator_amt
                        qa.save()

                        token = f"PASS-{uuid.uuid4().hex}"
                        QASessionAccess.objects.get_or_create(
                            session=qa,
                            email=pmt_tx.payer_email,
                            defaults={
                                "name": pmt_tx.payer_name or 'Pass Holder',
                                "access_token": token,
                                "transaction": pmt_tx
                            }
                        )
        except PaymentTransaction.DoesNotExist:
            pass

        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class CreatorWalletView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WalletSerializer

    def get_object(self):
        wallet, _ = Wallet.objects.get_or_create(user=self.request.user)
        return wallet


class CreatorTransactionsListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentTransactionSerializer

    def get_queryset(self):
        return PaymentTransaction.objects.filter(creator=self.request.user).order_by('-created_at')


class CreatorGiftsListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GiftSerializer

    def get_queryset(self):
        return Gift.objects.filter(creator=self.request.user).order_by('-created_at')


class CreatorLeaderboardView(views.APIView):
    permission_classes = [AllowAny]

    def get(self, request, username):
        creator = get_object_or_404(User, username=username)
        gifts = Gift.objects.filter(creator=creator).order_by('-amount')[:20]
        
        results = []
        for g in gifts:
            results.append({
                "id": str(g.id),
                "sender": "Anonymous Supporter" if g.is_anonymous else g.sender_alias,
                "amount": float(g.amount),
                "currency": g.currency,
                "badge": g.badge,
                "message": g.message,
                "created_at": g.created_at
            })
            
        total_supporters = Gift.objects.filter(creator=creator).count()
        return Response({
            "creator": creator.username,
            "total_supporters": total_supporters,
            "leaderboard": results
        }, status=status.HTTP_200_OK)


class BankListView(views.APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        country = request.query_params.get('country', 'NG')
        banks = FlutterwaveService.get_supported_banks(country=country)
        return Response({"banks": banks}, status=status.HTTP_200_OK)


class ResolveAccountView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        account_number = request.data.get('account_number', '').strip()
        bank_code = request.data.get('bank_code', '').strip()

        if not account_number or not bank_code:
            return Response({"error": "Account number and bank code are required"}, status=status.HTTP_400_BAD_REQUEST)

        res = FlutterwaveService.resolve_account_number(account_number, bank_code)
        if res.get('success'):
            return Response(res, status=status.HTTP_200_OK)
        return Response(res, status=status.HTTP_400_BAD_REQUEST)


class RequestPayoutView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        amount_raw = request.data.get('amount')
        
        try:
            amount = Decimal(str(amount_raw))
        except (TypeError, ValueError):
            return Response({"error": "Invalid amount format"}, status=status.HTTP_400_BAD_REQUEST)

        if amount < 1000:
            return Response({"error": "Minimum withdrawal amount is ₦1,000"}, status=status.HTTP_400_BAD_REQUEST)

        if wallet.balance < amount:
            return Response({"error": f"Insufficient wallet balance. Available: {wallet.currency} {wallet.balance:,.2f}"}, status=status.HTTP_400_BAD_REQUEST)

        bank_name = request.data.get('bank_name') or wallet.bank_name
        bank_code = request.data.get('bank_code') or wallet.bank_code
        account_number = request.data.get('account_number') or wallet.account_number
        account_name = request.data.get('account_name') or wallet.account_name

        if not bank_name or not account_number or not account_name:
            return Response({"error": "Complete bank account details are required for withdrawal."}, status=status.HTTP_400_BAD_REQUEST)

        with db_transaction.atomic():
            wallet.balance -= amount
            wallet.total_withdrawn += amount
            wallet.save()

            payout = PayoutRequest.objects.create(
                user=request.user,
                amount=amount,
                currency=wallet.currency,
                bank_name=bank_name,
                bank_code=bank_code,
                account_number=account_number,
                account_name=account_name,
                status='processing',
                note=f"Instant withdrawal payout to {account_name} ({bank_name})"
            )

        return Response({
            "success": True,
            "message": "Payout requested successfully! Funds are being processed to your bank account.",
            "payout": PayoutRequestSerializer(payout).data,
            "new_balance": str(wallet.balance)
        }, status=status.HTTP_201_CREATED)


class CheckQASessionAccessView(views.APIView):
    permission_classes = [AllowAny]

    def get(self, request, session_id):
        qa_session = get_object_or_404(QASession, id=session_id)
        
        # If free session, access is granted
        if not qa_session.is_paid or qa_session.price <= 0:
            return Response({"has_access": True, "is_paid": False}, status=status.HTTP_200_OK)

        # Check authenticated creator / host
        if request.user.is_authenticated and request.user == qa_session.host:
            return Response({"has_access": True, "is_host": True, "is_paid": True}, status=status.HTTP_200_OK)

        # Check access token or email
        token = request.query_params.get('token')
        email = request.query_params.get('email')

        has_access = False
        if token:
            has_access = QASessionAccess.objects.filter(session=qa_session, access_token=token).exists()
        elif email:
            has_access = QASessionAccess.objects.filter(session=qa_session, email__iexact=email.strip()).exists()

        return Response({
            "has_access": has_access,
            "is_paid": True,
            "price": str(qa_session.price),
            "currency": qa_session.currency,
            "perks": qa_session.paid_perks
        }, status=status.HTTP_200_OK)
