# backend/accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(unique=True)
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, blank=True, null=True)
    verification_token_created_at = models.DateTimeField(blank=True, null=True)
    reset_password_token = models.CharField(max_length=100, blank=True, null=True)
    reset_password_token_created_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    total_messages_received = models.IntegerField(default=0)
    last_active = models.DateTimeField(default=timezone.now)
    auto_delete_days = models.IntegerField(default=30)
    allow_voice_messages = models.BooleanField(default=True)
    public_message_wall = models.BooleanField(default=False)
    
    # Notification settings - make sure these are properly indented (4 spaces)
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    weekly_digest = models.BooleanField(default=False)
    
    # Privacy settings
    public_wall = models.BooleanField(default=True)
    allow_voice = models.BooleanField(default=True)
    auto_delete = models.BooleanField(default=False)
    
    def __str__(self):
        return self.username
    
    class Meta:
        ordering = ['-date_joined']