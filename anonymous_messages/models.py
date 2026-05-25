# backend/anonymous_messages/models.py
from django.db import models
from django.conf import settings

class AnonymousMessage(models.Model):
    MESSAGE_TYPES = [('text', 'Text'), ('voice', 'Voice'), ('image', 'Image')]
    
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='messages')
    content = models.TextField(max_length=2000)
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    media_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    reaction = models.CharField(max_length=10, blank=True, null=True)
    is_pinned = models.BooleanField(default=False)
    is_reported = models.BooleanField(default=False)
    report_reason = models.CharField(max_length=100, blank=True, null=True)
    sender_ip = models.GenericIPAddressField(blank=True, null=True)
    sender_session_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Archive fields
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Message to {self.recipient.username}"

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