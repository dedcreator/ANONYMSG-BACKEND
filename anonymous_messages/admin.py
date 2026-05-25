# backend/anonymous_messages/admin.py
from django.contrib import admin
from .models import AnonymousMessage, MessageReport

@admin.register(AnonymousMessage)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'recipient', 'created_at', 'is_read', 'is_reported']
    list_filter = ['is_read', 'is_reported', 'created_at']
    search_fields = ['recipient__username', 'content']

@admin.register(MessageReport)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'message', 'reason', 'created_at', 'resolved']
    list_filter = ['reason', 'resolved']