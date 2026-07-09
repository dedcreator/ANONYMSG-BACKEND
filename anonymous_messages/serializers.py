# backend/anonymous_messages/serializers.py
from rest_framework import serializers
from django.utils import timezone
from .models import (
    AnonymousMessage, 
    QASession, QAQuestion, QAAnswer, QAUpvote
)

# ============================================
# EXISTING SERIALIZERS
# ============================================

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

# ============================================
# Q&A SERIALIZERS - WITH UUID SUPPORT
# ============================================

class QAAnswerSerializer(serializers.ModelSerializer):
    answered_by_username = serializers.CharField(source='answered_by.username', read_only=True)
    
    class Meta:
        model = QAAnswer
        fields = ['id', 'answer', 'answered_by_username', 'created_at', 'updated_at']
        read_only_fields = ['id', 'answered_by', 'created_at', 'updated_at']

class QAQuestionSerializer(serializers.ModelSerializer):
    answer = QAAnswerSerializer(read_only=True)
    asked_by_username = serializers.SerializerMethodField()
    user_has_upvoted = serializers.SerializerMethodField()
    
    class Meta:
        model = QAQuestion
        fields = [
            'id', 'question', 'is_anonymous', 'is_answered', 'is_approved',
            'is_pinned', 'upvotes', 'asked_by_username', 'answer',
            'created_at', 'user_has_upvoted'
        ]
    
    def get_asked_by_username(self, obj):
        if obj.is_anonymous or not obj.asked_by:
            return "Anonymous"
        return obj.asked_by.username
    
    def get_user_has_upvoted(self, obj):
        request = self.context.get('request')
        if request:
            session_id = request.session.session_key
            if session_id:
                return QAUpvote.objects.filter(
                    question=obj, 
                    voter_session=session_id
                ).exists()
        return False

class QASessionSerializer(serializers.ModelSerializer):
    host_username = serializers.CharField(source='host.username', read_only=True)
    question_count = serializers.SerializerMethodField()
    questions = QAQuestionSerializer(many=True, read_only=True)
    is_host = serializers.SerializerMethodField()
    
    class Meta:
        model = QASession
        fields = [
            'id', 'title', 'description', 'is_active', 'is_live',
            'starts_at', 'ends_at', 'allow_anonymous', 'require_approval',
            'host_username', 'questions', 'question_count', 'is_host',
            'created_at', 'updated_at'
        ]
    
    def get_question_count(self, obj):
        return obj.questions.filter(is_approved=True).count()
    
    def get_is_host(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.host == request.user
        return False

class QASessionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = QASession
        fields = ['title', 'description', 'starts_at', 'ends_at', 'allow_anonymous', 'require_approval', 'max_questions']
    
    def validate(self, data):
        if data.get('starts_at') and data.get('ends_at'):
            if data['ends_at'] <= data['starts_at']:
                raise serializers.ValidationError("End time must be after start time")
        return data

class QAQuestionCreateSerializer(serializers.Serializer):
    session_id = serializers.UUIDField(required=True)
    question = serializers.CharField(max_length=500, required=True)
    is_anonymous = serializers.BooleanField(default=True)
    
    def validate_session_id(self, value):
        try:
            session = QASession.objects.get(id=value, is_active=True)
            if not session.is_live:
                raise serializers.ValidationError("This Q&A session is not currently live")
            
            if session.questions.count() >= session.max_questions:
                raise serializers.ValidationError("This session has reached the maximum number of questions")
            
            return value
        except QASession.DoesNotExist:
            raise serializers.ValidationError("Session not found or inactive")

class QAAnswerCreateSerializer(serializers.Serializer):
    question_id = serializers.UUIDField(required=True)
    answer = serializers.CharField(max_length=2000, required=True)