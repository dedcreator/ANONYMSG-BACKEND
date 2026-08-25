# backend/anonymous_messages/views.py
import os
import uuid
import hashlib
from datetime import datetime
from decimal import Decimal
from rest_framework import generics, status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings

from .models import (
    AnonymousMessage, MessageReport,
    QASession, QAQuestion, QAAnswer, QAUpvote
)
from .serializers import (
    AnonymousMessageSerializer,
    PublicWallMessageSerializer,
    SendMessageSerializer,
    ReplyMessageSerializer,
    ReportMessageSerializer,
    QASessionSerializer,
    QASessionCreateSerializer,
    QAQuestionSerializer,
    QAQuestionCreateSerializer,
    QAAnswerSerializer,
    QAAnswerCreateSerializer,
)
from accounts.models import User

# ============================================
# RATE LIMITER HELPERS
# ============================================

class RateLimiter:
    """Simple rate limiter using Django's cache"""
    
    def __init__(self, key, limit, period, block_duration=None):
        self.key = key
        self.limit = limit
        self.period = period
        self.block_duration = block_duration or period
        
    def is_allowed(self):
        block_key = f"blocked_{self.key}"
        if cache.get(block_key):
            return False
        
        count_key = f"ratelimit_{self.key}"
        current_count = cache.get(count_key, 0)
        
        if current_count >= self.limit:
            cache.set(block_key, True, self.block_duration)
            return False
        
        cache.set(count_key, current_count + 1, self.period)
        return True
    
    def get_remaining(self):
        count_key = f"ratelimit_{self.key}"
        current_count = cache.get(count_key, 0)
        return max(0, self.limit - current_count)
    
    def get_reset_time(self):
        return self.period


class VoteValidator:
    """Prevents duplicate voting using device fingerprinting"""
    
    @staticmethod
    def get_device_fingerprint(request):
        ip = request.META.get('REMOTE_ADDR', '')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        session_id = request.session.session_key or ''
        
        fingerprint_string = f"{ip}|{user_agent}|{accept_language}|{session_id}"
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:32]


# ============================================
# MESSAGE VIEWS
# ============================================

class InboxPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class InboxView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AnonymousMessageSerializer
    pagination_class = InboxPagination
    
    def get_queryset(self):
        user = self.request.user
        filter_type = self.request.query_params.get('type')
        qs = AnonymousMessage.objects.filter(recipient=user, is_archived=False)
        
        if filter_type == 'voice':
            qs = qs.filter(message_type='voice')
        elif filter_type == 'image':
            qs = qs.filter(message_type='image')
        elif filter_type == 'gif':
            qs = qs.filter(message_type='gif')
        elif filter_type == 'pinned':
            qs = qs.filter(is_pinned=True)
        elif filter_type == 'super':
            qs = qs.filter(is_super_message=True)
            
        return qs


class ArchivedMessagesView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AnonymousMessageSerializer
    pagination_class = InboxPagination
    
    def get_queryset(self):
        return AnonymousMessage.objects.filter(
            recipient=self.request.user, 
            is_archived=True
        )


class PublicWallView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicWallMessageSerializer
    pagination_class = InboxPagination
    
    def get_queryset(self):
        username = self.kwargs.get('username')
        user = get_object_or_404(User, username=username)
        return AnonymousMessage.objects.filter(
            recipient=user,
            is_archived=False,
            is_public_on_wall=True
        ).order_by('-is_pinned', '-created_at')


class SendMessageView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = SendMessageSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        recipient_username = serializer.validated_data['recipient_username']
        try:
            recipient = User.objects.get(username=recipient_username)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        gift_amount = serializer.validated_data.get('gift_amount', Decimal('0.00'))
        is_super = serializer.validated_data.get('is_super_message', False) or gift_amount > 0
        super_color = serializer.validated_data.get('super_message_color', 'gold')
        
        message = AnonymousMessage.objects.create(
            recipient=recipient,
            content=serializer.validated_data['content'],
            message_type=serializer.validated_data.get('message_type', 'text'),
            gift_amount=gift_amount,
            gift_currency=serializer.validated_data.get('gift_currency', 'NGN'),
            is_super_message=is_super,
            super_message_color=super_color,
            sender_ip=self.get_client_ip(request),
        )
        
        recipient.total_messages_received += 1
        recipient.save()
        
        return Response({
            'success': True,
            'message_id': str(message.id),
            'created_at': message.created_at
        }, status=status.HTTP_201_CREATED)
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SendVoiceMessageView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        recipient_username = request.data.get('recipient_username')
        voice_file = request.FILES.get('voice_file')
        duration = request.data.get('duration', 0)
        
        if not recipient_username:
            return Response({'error': 'recipient_username is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not voice_file:
            return Response({'error': 'voice_file is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            recipient = User.objects.get(username=recipient_username)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Save the voice file
        file_name = f"voice_{uuid.uuid4()}.webm"
        file_path = default_storage.save(f"voice_messages/{file_name}", ContentFile(voice_file.read()))
        media_url = f"{settings.MEDIA_URL}{file_path}"
        
        # Create message
        message = AnonymousMessage.objects.create(
            recipient=recipient,
            content="Voice message",
            message_type='voice',
            media_url=media_url,
            media_duration=int(duration),
            sender_ip=self.get_client_ip(request),
        )
        
        recipient.total_messages_received += 1
        recipient.save()
        
        return Response({
            'success': True,
            'message_id': str(message.id),
            'media_url': media_url,
            'created_at': message.created_at
        }, status=status.HTTP_201_CREATED)
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SendImageMessageView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        recipient_username = request.data.get('recipient_username')
        image_file = request.FILES.get('image_file')
        
        if not recipient_username:
            return Response({'error': 'recipient_username is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not image_file:
            return Response({'error': 'image_file is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            recipient = User.objects.get(username=recipient_username)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            images_dir = os.path.join(settings.MEDIA_ROOT, 'images')
            if not os.path.exists(images_dir):
                os.makedirs(images_dir, exist_ok=True)
            
            file_extension = os.path.splitext(image_file.name)[1]
            file_name = f"image_{uuid.uuid4()}{file_extension}"
            saved_path = default_storage.save(f"images/{file_name}", ContentFile(image_file.read()))
            media_url = f"{settings.MEDIA_URL}{saved_path}"
            
            message = AnonymousMessage.objects.create(
                recipient=recipient,
                content="Image attachment",
                message_type='image',
                media_url=media_url,
                sender_ip=self.get_client_ip(request),
            )
            
            recipient.total_messages_received += 1
            recipient.save()
            
            return Response({
                'success': True,
                'message_id': str(message.id),
                'media_url': media_url,
                'created_at': message.created_at.isoformat()
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class MessageDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AnonymousMessageSerializer
    
    def get_queryset(self):
        return AnonymousMessage.objects.filter(recipient=self.request.user)


class MarkAsReadView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        try:
            message = AnonymousMessage.objects.get(id=pk, recipient=request.user)
            message.is_read = True
            message.read_at = timezone.now()
            message.save()
            return Response({'success': True})
        except AnonymousMessage.DoesNotExist:
            return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)


class ReactMessageView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        message = get_object_or_404(AnonymousMessage, id=pk, recipient=request.user)
        reaction = request.data.get('reaction', '').strip()
        message.reaction = reaction
        message.save()
        return Response({'success': True, 'reaction': message.reaction})


class ReplyMessageView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        message = get_object_or_404(AnonymousMessage, id=pk, recipient=request.user)
        serializer = ReplyMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        message.creator_reply = serializer.validated_data['creator_reply']
        message.replied_at = timezone.now()
        if serializer.validated_data.get('publish_to_wall'):
            message.is_public_on_wall = True
        message.save()
        
        return Response({
            'success': True,
            'message': AnonymousMessageSerializer(message).data
        })


class ToggleWallMessageView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        message = get_object_or_404(AnonymousMessage, id=pk, recipient=request.user)
        is_public = request.data.get('is_public', not message.is_public_on_wall)
        message.is_public_on_wall = is_public
        message.save()
        return Response({'success': True, 'is_public_on_wall': message.is_public_on_wall})


class PinMessageView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        message = get_object_or_404(AnonymousMessage, id=pk, recipient=request.user)
        message.is_pinned = True
        message.save()
        return Response({'success': True, 'is_pinned': True})


class UnpinMessageView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        message = get_object_or_404(AnonymousMessage, id=pk, recipient=request.user)
        message.is_pinned = False
        message.save()
        return Response({'success': True, 'is_pinned': False})


class ArchiveMessageView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        message = get_object_or_404(AnonymousMessage, id=pk, recipient=request.user)
        message.is_archived = True
        message.archived_at = timezone.now()
        message.save()
        return Response({'success': True, 'archived': True})


class RestoreMessageView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        message = get_object_or_404(AnonymousMessage, id=pk, recipient=request.user, is_archived=True)
        message.is_archived = False
        message.archived_at = None
        message.save()
        return Response({'success': True, 'restored': True})


class DeleteMessageView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, pk):
        message = get_object_or_404(AnonymousMessage, id=pk, recipient=request.user)
        message.delete()
        return Response({'success': True})


class PermanentDeleteView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, pk):
        message = get_object_or_404(AnonymousMessage, id=pk, recipient=request.user, is_archived=True)
        message.delete()
        return Response({'success': True})


class ReportMessageView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        message = get_object_or_404(AnonymousMessage, id=pk, recipient=request.user)
        serializer = ReportMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        message.is_reported = True
        message.report_reason = serializer.validated_data['reason']
        message.save()
        
        MessageReport.objects.create(
            message=message,
            reported_by=request.user,
            reason=serializer.validated_data['reason'],
            description=serializer.validated_data.get('description', '')
        )
        return Response({'success': True})


class StatsView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        messages = AnonymousMessage.objects.filter(recipient=request.user)
        total_active = messages.filter(is_archived=False).count()
        unread_count = messages.filter(is_read=False, is_archived=False).count()
        voice_count = messages.filter(message_type='voice', is_archived=False).count()
        super_count = messages.filter(is_super_message=True, is_archived=False).count()
        
        wallet = getattr(request.user, 'wallet', None)
        total_earnings = float(wallet.total_earned) if wallet else 0.0
        
        return Response({
            'total': total_active,
            'unread': unread_count,
            'voice_count': voice_count,
            'super_messages': super_count,
            'total_earnings': total_earnings,
            'response_rate': 92,
            'streak': 12,
        })


# ============================================
# Q&A VIEWS
# ============================================

class QASessionListView(generics.ListCreateAPIView):
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [AllowAny()]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return QASessionCreateSerializer
        return QASessionSerializer
    
    def get_queryset(self):
        queryset = QASession.objects.filter(is_active=True)
        if self.request.query_params.get('live') == 'true':
            queryset = queryset.filter(is_live=True)
        if self.request.query_params.get('host'):
            queryset = queryset.filter(host__username=self.request.query_params.get('host'))
        return queryset
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def perform_create(self, serializer):
        serializer.save(host=self.request.user)


class QASessionDetailView(generics.RetrieveUpdateDestroyAPIView):
    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAuthenticated()]
        return [AllowAny()]
    
    serializer_class = QASessionSerializer
    lookup_field = 'id'
    
    def get_queryset(self):
        return QASession.objects.all()
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def update(self, request, *args, **kwargs):
        session = self.get_object()
        if session.host != request.user:
            return Response({'error': 'You can only update your own sessions'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)


class QASessionLiveView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, id):
        session = get_object_or_404(QASession, id=id, host=request.user)
        is_live = request.data.get('is_live', not session.is_live)
        session.is_live = is_live
        session.save()
        return Response({'success': True, 'is_live': session.is_live})


class QAQuestionListView(generics.ListCreateAPIView):
    permission_classes = [AllowAny]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return QAQuestionCreateSerializer
        return QAQuestionSerializer
    
    def get_queryset(self):
        session_id = self.request.query_params.get('session_id')
        if not session_id:
            return QAQuestion.objects.none()
        
        filter_status = self.request.query_params.get('filter')
        qs = QAQuestion.objects.filter(session_id=session_id, is_approved=True)
        
        if filter_status == 'answered':
            qs = qs.filter(is_answered=True)
        elif filter_status == 'unanswered':
            qs = qs.filter(is_answered=False)
        elif filter_status == 'super':
            qs = qs.filter(is_super_question=True)
            
        return qs
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        session = get_object_or_404(QASession, id=serializer.validated_data['session_id'])
        
        # Check if session is paid and check pass
        if session.is_paid and session.price > 0:
            pass_token = request.headers.get('X-QA-Pass-Token') or request.data.get('access_token')
            from payments.models import QASessionAccess
            has_pass = QASessionAccess.objects.filter(session=session, access_token=pass_token).exists() if pass_token else False
            is_host = request.user.is_authenticated and session.host == request.user
            if not has_pass and not is_host:
                return Response({'error': 'A paid access pass is required to submit questions in this VIP session.'}, status=status.HTTP_403_FORBIDDEN)
        
        session_id_key = request.session.session_key or uuid.uuid4().hex
        
        is_super = serializer.validated_data.get('is_super_question', False)
        gift_amount = serializer.validated_data.get('gift_amount', Decimal('0.00'))
        
        question = QAQuestion.objects.create(
            session=session,
            question=serializer.validated_data['question'],
            is_anonymous=serializer.validated_data.get('is_anonymous', True),
            asker_name=serializer.validated_data.get('asker_name', ''),
            asked_by=request.user if request.user.is_authenticated else None,
            is_super_question=is_super or gift_amount > 0,
            gift_amount=gift_amount,
            gift_currency=serializer.validated_data.get('gift_currency', 'NGN'),
            questioner_session=session_id_key,
            is_approved=not session.require_approval
        )
        
        return Response({
            'success': True,
            'data': QAQuestionSerializer(question, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)


class QAQuestionUpvoteView(views.APIView):
    permission_classes = [AllowAny]
    
    def post(self, request, pk):
        question = get_object_or_404(QAQuestion, id=pk, is_approved=True)
        
        session_id = request.session.session_key
        if not session_id:
            request.session.create()
            session_id = request.session.session_key
        
        upvote, created = QAUpvote.objects.get_or_create(
            question=question,
            voter_session=session_id
        )
        
        if not created:
            # Toggle upvote off
            upvote.delete()
            question.upvotes = max(0, question.upvotes - 1)
            question.save()
            return Response({'success': True, 'upvoted': False, 'upvotes': question.upvotes})
        
        question.upvotes += 1
        question.save()
        return Response({'success': True, 'upvoted': True, 'upvotes': question.upvotes})


class QAQuestionPinView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        question = get_object_or_404(QAQuestion, id=pk)
        if question.session.host != request.user:
            return Response({'error': 'Only the host can pin questions'}, status=status.HTTP_403_FORBIDDEN)
        
        is_pinned = request.data.get('is_pinned', not question.is_pinned)
        question.is_pinned = is_pinned
        question.save()
        return Response({'success': True, 'is_pinned': question.is_pinned})


class QAAnswerView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = QAAnswerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        question = get_object_or_404(QAQuestion, id=serializer.validated_data['question_id'])
        if question.session.host != request.user:
            return Response({'error': 'Only the host can answer questions'}, status=status.HTTP_403_FORBIDDEN)
        
        answer, created = QAAnswer.objects.update_or_create(
            question=question,
            defaults={
                'answer': serializer.validated_data['answer'],
                'media_url': serializer.validated_data.get('media_url', ''),
                'answered_by': request.user
            }
        )
        
        question.is_answered = True
        question.save()
        
        return Response({
            'success': True,
            'data': QAAnswerSerializer(answer).data
        }, status=status.HTTP_200_OK)