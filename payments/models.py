# backend/payments/models.py
import uuid
from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from anonymous_messages.models import QASession, AnonymousMessage


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='wallet'
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_withdrawn = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=10, default='NGN')
    
    # Creator Payout Bank Details
    bank_name = models.CharField(max_length=100, blank=True, default='')
    bank_code = models.CharField(max_length=20, blank=True, default='')
    account_number = models.CharField(max_length=30, blank=True, default='')
    account_name = models.CharField(max_length=100, blank=True, default='')
    
    # Settings
    minimum_gift_amount = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    allow_gifting = models.BooleanField(default=True)
    show_leaderboard = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s Wallet ({self.currency} {self.balance})"


class PaymentTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('gift', 'Direct Creator Gift'),
        ('paid_qa_access', 'Paid Q&A Session Pass'),
        ('super_question', 'Super Question Boost'),
        ('super_message', 'Super Message Tip'),
        ('payout', 'Creator Withdrawal Payout'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('successful', 'Successful'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tx_ref = models.CharField(max_length=120, unique=True, db_index=True)
    flw_ref = models.CharField(max_length=120, blank=True, null=True)
    flw_transaction_id = models.CharField(max_length=120, blank=True, null=True)
    
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPES, default='gift')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='NGN')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_transactions'
    )
    
    payer_email = models.EmailField(blank=True, null=True)
    payer_name = models.CharField(max_length=100, blank=True, null=True)
    is_anonymous = models.BooleanField(default=True)
    donor_alias = models.CharField(max_length=100, blank=True, null=True, default='Generous Anon')
    gift_note = models.TextField(blank=True, null=True)
    
    qa_session = models.ForeignKey(
        QASession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='session_transactions'
    )
    message = models.ForeignKey(
        AnonymousMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='message_transactions'
    )
    
    meta_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.transaction_type} - {self.tx_ref} ({self.currency} {self.amount}) - {self.status}"


class Gift(models.Model):
    BADGE_CHOICES = [
        ('Bronze Supporter', 'Bronze Supporter'),
        ('Silver VIP', 'Silver VIP'),
        ('Gold Champion', 'Gold Champion'),
        ('Diamond Legend', 'Diamond Legend'),
        ('Angel Backer', 'Angel Backer'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.OneToOneField(
        PaymentTransaction,
        on_delete=models.CASCADE,
        related_name='gift_detail'
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_gifts'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='NGN')
    sender_alias = models.CharField(max_length=100, default='Generous Anon')
    is_anonymous = models.BooleanField(default=True)
    message = models.TextField(blank=True, null=True)
    badge = models.CharField(max_length=30, choices=BADGE_CHOICES, default='Bronze Supporter')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Gift {self.currency} {self.amount} to {self.creator.username}"


class QASessionAccess(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        QASession,
        on_delete=models.CASCADE,
        related_name='ticket_accesses'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='qa_session_passes'
    )
    email = models.EmailField()
    name = models.CharField(max_length=100, blank=True, default='Pass Holder')
    access_token = models.CharField(max_length=120, unique=True, db_index=True)
    transaction = models.ForeignKey(
        PaymentTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='access_records'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['session', 'email']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Pass for {self.email} -> {self.session.title}"


class PayoutRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('processing', 'Processing Flutterwave Transfer'),
        ('completed', 'Completed / Paid'),
        ('rejected', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payout_requests'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='NGN')
    bank_name = models.CharField(max_length=100)
    bank_code = models.CharField(max_length=20, blank=True)
    account_number = models.CharField(max_length=30)
    account_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    flw_transfer_id = models.CharField(max_length=100, blank=True, null=True)
    note = models.TextField(blank=True, default='')
    
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Payout {self.currency} {self.amount} for {self.user.username} ({self.status})"


# Auto-create wallet for each user
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_wallet(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.get_or_create(user=instance)

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_wallet(sender, instance, **kwargs):
    if hasattr(instance, 'wallet'):
        instance.wallet.save()
