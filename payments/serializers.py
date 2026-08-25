# backend/payments/serializers.py
from rest_framework import serializers
from .models import Wallet, PaymentTransaction, Gift, QASessionAccess, PayoutRequest
from anonymous_messages.models import QASession
from accounts.models import User


class WalletSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Wallet
        fields = [
            'username', 'balance', 'total_earned', 'total_withdrawn', 'currency',
            'bank_name', 'bank_code', 'account_number', 'account_name',
            'minimum_gift_amount', 'allow_gifting', 'show_leaderboard',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['balance', 'total_earned', 'total_withdrawn', 'created_at', 'updated_at']


class PaymentTransactionSerializer(serializers.ModelSerializer):
    creator_username = serializers.CharField(source='creator.username', read_only=True)
    
    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'tx_ref', 'flw_ref', 'transaction_type', 'amount', 'currency',
            'status', 'creator_username', 'payer_email', 'payer_name',
            'is_anonymous', 'donor_alias', 'gift_note', 'qa_session',
            'message', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class GiftSerializer(serializers.ModelSerializer):
    creator_username = serializers.CharField(source='creator.username', read_only=True)
    display_sender = serializers.SerializerMethodField()
    
    class Meta:
        model = Gift
        fields = [
            'id', 'creator_username', 'amount', 'currency', 'display_sender',
            'is_anonymous', 'message', 'badge', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
        
    def get_display_sender(self, obj):
        if obj.is_anonymous:
            return obj.sender_alias or 'Generous Anon'
        return obj.sender_alias or 'Generous Supporter'


class InitializeGiftSerializer(serializers.Serializer):
    creator_username = serializers.CharField(required=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=True, min_value=100)
    currency = serializers.CharField(required=False, default='NGN')
    sender_alias = serializers.CharField(required=False, allow_blank=True, default='Generous Anon')
    is_anonymous = serializers.BooleanField(required=False, default=True)
    message = serializers.CharField(required=False, allow_blank=True, default='')
    payer_email = serializers.EmailField(required=False, allow_blank=True, default='supporter@anonymsg.com')
    redirect_url = serializers.URLField(required=False)


class InitializeQAPassSerializer(serializers.Serializer):
    session_id = serializers.UUIDField(required=True)
    email = serializers.EmailField(required=True)
    name = serializers.CharField(required=False, allow_blank=True, default='Pass Holder')
    redirect_url = serializers.URLField(required=False)


class VerifyPaymentSerializer(serializers.Serializer):
    tx_ref = serializers.CharField(required=True)
    transaction_id = serializers.CharField(required=False, allow_blank=True, default='')


class PayoutRequestSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = PayoutRequest
        fields = [
            'id', 'username', 'amount', 'currency', 'bank_name', 'bank_code',
            'account_number', 'account_name', 'status', 'note', 'created_at', 'processed_at'
        ]
        read_only_fields = ['id', 'status', 'created_at', 'processed_at']


class QASessionAccessSerializer(serializers.ModelSerializer):
    session_title = serializers.CharField(source='session.title', read_only=True)
    
    class Meta:
        model = QASessionAccess
        fields = ['id', 'session', 'session_title', 'email', 'name', 'access_token', 'created_at']
        read_only_fields = ['id', 'access_token', 'created_at']
