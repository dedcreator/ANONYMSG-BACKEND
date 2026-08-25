# backend/anonymous_messages/serializers.py
from rest_framework import serializers
from django.utils import timezone
from .models import (
    AnonymousMessage, 
    QASession, QAQuestion, QAAnswer, QAUpvote
)

# ============================================
# MESSAGE SERIALIZERS
# ============================================

class AnonymousMessageSerializer(serializers.ModelSerializer):
    recipient_username = serializers.CharField(source='recipient.username', read_only=True)
    
    class Meta:
        model = AnonymousMessage
        fields = [
            'id', 'recipient_username', 'content', 'message_type', 'media_url',
            'media_duration', 'media_thumbnail', 'created_at', 'is_read', 'reaction',
            'is_pinned', 'is_archived', 'is_public_on_wall', 'creator_reply',
            'replied_at', 'gift_amount', 'gift_currency', 'is_super_message',
            'super_message_color'
        ]
        read_only_fields = ['id', 'created_at', 'is_read', 'recipient_username']


class PublicWallMessageSerializer(serializers.ModelSerializer):
    recipient_username = serializers.CharField(source='recipient.username', read_only=True)
    
    class Meta:
        model = AnonymousMessage
        fields = [
            'id', 'recipient_username', 'content', 'message_type', 'media_url',
            'created_at', 'reaction', 'is_pinned', 'creator_reply', 'replied_at',
            'gift_amount', 'gift_currency', 'is_super_message', 'super_message_color'
        ]


class SendMessageSerializer(serializers.Serializer):
    recipient_username = serializers.CharField(required=True, max_length=50)
    content = serializers.CharField(required=True, max_length=2000)
    message_type = serializers.ChoiceField(choices=['text', 'voice', 'image', 'gif'], default='text')
    gift_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0.00)
    gift_currency = serializers.CharField(required=False, default='NGN')
    is_super_message = serializers.BooleanField(required=False, default=False)
    super_message_color = serializers.CharField(required=False, allow_blank=True, default='gold')


class ReplyMessageSerializer(serializers.Serializer):
    creator_reply = serializers.CharField(required=True, max_length=2000)
    publish_to_wall = serializers.BooleanField(required=False, default=False)


class ReportMessageSerializer(serializers.Serializer):
    reason = serializers.ChoiceField(choices=['spam', 'harassment', 'hate_speech', 'inappropriate', 'other'])
    description = serializers.CharField(required=False, allow_blank=True)


# ============================================
# Q&A SERIALIZERS
# ============================================

class QAAnswerSerializer(serializers.ModelSerializer):
    answered_by_username = serializers.CharField(source='answered_by.username', read_only=True)
    
    class Meta:
        model = QAAnswer
        fields = ['id', 'answer', 'media_url', 'answered_by_username', 'created_at', 'updated_at']
        read_only_fields = ['id', 'answered_by', 'created_at', 'updated_at']


class QAQuestionSerializer(serializers.ModelSerializer):
    answer = QAAnswerSerializer(read_only=True)
    asked_by_username = serializers.SerializerMethodField()
    user_has_upvoted = serializers.SerializerMethodField()
    
    class Meta:
        model = QAQuestion
        fields = [
            'id', 'question', 'is_anonymous', 'asker_name', 'is_answered', 'is_approved',
            'is_pinned', 'upvotes', 'is_super_question', 'gift_amount', 'gift_currency',
            'asked_by_username', 'answer', 'created_at', 'user_has_upvoted'
        ]
    
    def get_asked_by_username(self, obj):
        if obj.is_anonymous or not obj.asked_by:
            return obj.asker_name or "Anonymous"
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
    has_access = serializers.SerializerMethodField()
    
    class Meta:
        model = QASession
        fields = [
            'id', 'title', 'description', 'is_active', 'is_live',
            'starts_at', 'ends_at', 'allow_anonymous', 'require_approval',
            'is_paid', 'price', 'currency', 'paid_perks', 'total_revenue',
            'host_username', 'questions', 'question_count', 'is_host', 'has_access',
            'created_at', 'updated_at'
        ]
    
    def get_question_count(self, obj):
        return obj.questions.filter(is_approved=True).count()
    
    def get_is_host(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.host == request.user
        return False

    def get_has_access(self, obj):
        if not obj.is_paid or obj.price <= 0:
            return True
        request = self.context.get('request')
        if not request:
            return False
        if request.user.is_authenticated and obj.host == request.user:
            return True
        # Check pass from header or query param
        token = request.query_params.get('token') or request.headers.get('X-QA-Pass-Token')
        if token:
            from payments.models import QASessionAccess
            return QASessionAccess.objects.filter(session=obj, access_token=token).exists()
        return False


class QASessionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = QASession
        fields = [
            'title', 'description', 'starts_at', 'ends_at', 'allow_anonymous',
            'require_approval', 'max_questions', 'is_paid', 'price', 'currency', 'paid_perks'
        ]
    
    def validate(self, data):
        if data.get('starts_at') and data.get('ends_at'):
            if data['ends_at'] <= data['starts_at']:
                raise serializers.ValidationError("End time must be after start time")
        return data


class QAQuestionCreateSerializer(serializers.Serializer):
    session_id = serializers.UUIDField(required=True)
    question = serializers.CharField(max_length=500, required=True)
    is_anonymous = serializers.BooleanField(default=True)
    asker_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    is_super_question = serializers.BooleanField(default=False)
    gift_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0.00)
    gift_currency = serializers.CharField(required=False, default='NGN')
    
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
    media_url = serializers.URLField(required=False, allow_blank=True)