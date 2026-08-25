# backend/anonymous_messages/models.py
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

class AnonymousMessage(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Text'), 
        ('voice', 'Voice'), 
        ('image', 'Image'),
        ('gif', 'GIF')
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='messages')
    content = models.TextField(max_length=2000, blank=True, null=True)
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    media_url = models.URLField(blank=True, null=True)
    media_duration = models.IntegerField(blank=True, null=True)  # For voice messages in seconds
    media_thumbnail = models.URLField(blank=True, null=True)  # For image thumbnails
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    reaction = models.CharField(max_length=10, blank=True, null=True)
    is_pinned = models.BooleanField(default=False)
    is_reported = models.BooleanField(default=False)
    report_reason = models.CharField(max_length=100, blank=True, null=True)
    sender_ip = models.GenericIPAddressField(blank=True, null=True)
    sender_session_id = models.CharField(max_length=100, blank=True, null=True)
    
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(blank=True, null=True)
    
    # Public Wall & Creator Replies
    is_public_on_wall = models.BooleanField(default=False)
    creator_reply = models.TextField(max_length=2000, blank=True, null=True)
    replied_at = models.DateTimeField(blank=True, null=True)
    
    # Gifting & Super Messages
    gift_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    gift_currency = models.CharField(max_length=10, default='NGN')
    is_super_message = models.BooleanField(default=False)
    super_message_color = models.CharField(max_length=30, blank=True, null=True)
    
    class Meta:
        ordering = ['-is_pinned', '-created_at']  # Pinned messages first
    
    def __str__(self):
        return f"{self.message_type} message to {self.recipient.username}"

class MessageReport(models.Model):
    REASON_CHOICES = [
        ('spam', 'Spam'), ('harassment', 'Harassment'),
        ('hate_speech', 'Hate Speech'), ('inappropriate', 'Inappropriate Content'), ('other', 'Other')
    ]
    
    message = models.ForeignKey(AnonymousMessage, on_delete=models.CASCADE, related_name='reports')
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Report for message {self.message.id}"

# ============================================
# Q&A MODELS - WITH PAID SESSION & SUPER QUESTIONS
# ============================================

class QASession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='qa_sessions'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(max_length=1000, blank=True)
    is_active = models.BooleanField(default=True)
    is_live = models.BooleanField(default=False)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    allow_anonymous = models.BooleanField(default=True)
    require_approval = models.BooleanField(default=False)
    max_questions = models.IntegerField(default=100)
    
    # Paid Q&A Session Features
    is_paid = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=10, default='NGN')
    paid_perks = models.TextField(blank=True, default='Access to private live Q&A stream, priority question submission, and exclusive creator answers.')
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-starts_at']
    
    def __str__(self):
        return f"Q&A: {self.title[:50]}"

class QAQuestion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(QASession, on_delete=models.CASCADE, related_name='questions')
    question = models.TextField(max_length=500)
    asked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='qa_questions'
    )
    asker_name = models.CharField(max_length=100, blank=True, null=True)
    is_anonymous = models.BooleanField(default=True)
    is_answered = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    is_pinned = models.BooleanField(default=False)
    upvotes = models.IntegerField(default=0)
    
    # Super Question / Attached Gift
    is_super_question = models.BooleanField(default=False)
    gift_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    gift_currency = models.CharField(max_length=10, default='NGN')
    
    created_at = models.DateTimeField(auto_now_add=True)
    questioner_session = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        ordering = ['-is_pinned', '-is_super_question', '-upvotes', 'created_at']
    
    def __str__(self):
        return f"Q: {self.question[:50]}"

class QAAnswer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.OneToOneField(QAQuestion, on_delete=models.CASCADE, related_name='answer')
    answer = models.TextField(max_length=2000)
    answered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='qa_answers'
    )
    media_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"A: {self.answer[:50]}"

class QAUpvote(models.Model):
    question = models.ForeignKey(QAQuestion, on_delete=models.CASCADE, related_name='upvote_set')
    voter_session = models.CharField(max_length=100, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['question', 'voter_session']
    
    def __str__(self):
        return f"Upvote on Q{self.question.id}"