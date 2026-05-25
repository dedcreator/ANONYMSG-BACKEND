# backend/anonymous_messages/serializers.py
from rest_framework import serializers
from .models import AnonymousMessage

class AnonymousMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnonymousMessage
        fields = ['id', 'content', 'message_type', 'media_url', 'created_at', 'is_read', 'reaction', 'is_pinned']
        read_only_fields = ['id', 'created_at', 'is_read']

class SendMessageSerializer(serializers.Serializer):
    recipient_username = serializers.CharField(required=True, max_length=50)
    content = serializers.CharField(required=True, max_length=2000)
    message_type = serializers.ChoiceField(choices=['text', 'voice', 'image'], default='text')

class ReportMessageSerializer(serializers.Serializer):
    reason = serializers.ChoiceField(choices=['spam', 'harassment', 'hate_speech', 'inappropriate', 'other'])
    description = serializers.CharField(required=False, allow_blank=True)