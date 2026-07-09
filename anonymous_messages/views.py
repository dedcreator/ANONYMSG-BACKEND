# backend/anonymous_messages/views.py
import uuid
import hashlib
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.core.cache import cache

from .models import (
    AnonymousMessage, MessageReport,
    QASession, QAQuestion, QAAnswer, QAUpvote
)
from .serializers import (
    AnonymousMessageSerializer,
    SendMessageSerializer,
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
# EXISTING MESSAGE VIEWS
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
        return AnonymousMessage.objects.filter(
            recipient=self.request.user, 
            is_archived=False
        )

class ArchivedMessagesView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AnonymousMessageSerializer
    pagination_class = InboxPagination
    
    def get_queryset(self):
        return AnonymousMessage.objects.filter(
            recipient=self.request.user, 
            is_archived=True
        )

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
        
        message = AnonymousMessage.objects.create(
            recipient=recipient,
            content=serializer.validated_data['content'],
            message_type=serializer.validated_data.get('message_type', 'text'),
            sender_ip=self.get_client_ip(request),
        )
        
        recipient.total_messages_received += 1
        recipient.save()
        
        return Response({
            'success': True,
            'message_id': message.id,
            'created_at': message.created_at
        }, status=status.HTTP_201_CREATED)
    
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

class DeleteMessageView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, pk):
        try:
            message = AnonymousMessage.objects.get(id=pk, recipient=request.user)
            message.delete()
            return Response({'success': True})
        except AnonymousMessage.DoesNotExist:
            return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)

class ArchiveMessageView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        try:
            message = AnonymousMessage.objects.get(id=pk, recipient=request.user)
            message.is_archived = True
            message.archived_at = timezone.now()
            message.save()
            return Response({'success': True, 'archived': True})
        except AnonymousMessage.DoesNotExist:
            return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)

class RestoreMessageView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        try:
            message = AnonymousMessage.objects.get(id=pk, recipient=request.user, is_archived=True)
            message.is_archived = False
            message.archived_at = None
            message.save()
            return Response({'success': True, 'restored': True})
        except AnonymousMessage.DoesNotExist:
            return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)

class PermanentDeleteView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, pk):
        try:
            message = AnonymousMessage.objects.get(id=pk, recipient=request.user, is_archived=True)
            message.delete()
            return Response({'success': True})
        except AnonymousMessage.DoesNotExist:
            return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)

class ReportMessageView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReportMessageSerializer
    
    def post(self, request, pk):
        try:
            message = AnonymousMessage.objects.get(id=pk, recipient=request.user)
            message.is_reported = True
            message.report_reason = request.data.get('reason')
            message.save()
            
            MessageReport.objects.create(
                message=message,
                reported_by=request.user,
                reason=request.data.get('reason'),
                description=request.data.get('description', '')
            )
            
            return Response({'success': True})
        except AnonymousMessage.DoesNotExist:
            return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)

class StatsView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        messages = AnonymousMessage.objects.filter(recipient=request.user)
        from datetime import datetime
        
        stats = {
            'total': messages.filter(is_archived=False).count(),
            'unread': messages.filter(is_read=False, is_archived=False).count(),
            'this_week': messages.filter(created_at__week=datetime.now().isocalendar()[1], is_archived=False).count(),
            'avg_response_time': '2.4h',
            'top_reaction': '🔥',
            'streak': 7,
            'response_rate': 85,
        }
        return Response(stats)


# ============================================
# Q&A VIEWS - WITH RATE LIMITING
# ============================================

class QASessionListView(generics.ListCreateAPIView):
    """List Q&A sessions or create a new one with rate limiting"""
    
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
        queryset = queryset.filter(starts_at__gte=timezone.now())
        
        if self.request.query_params.get('live') == 'true':
            queryset = queryset.filter(is_live=True)
        
        return queryset
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        # Rate limiting: 50 sessions per hour per user
        limiter = RateLimiter(
            key=f"qa_session_create_{request.user.id}",
            limit=50,
            period=3600  # 1 hour
        )
        
        if not limiter.is_allowed():
            return Response({
                'error': 'Rate limit exceeded. You can only create 50 sessions per hour.',
                'remaining': 0,
                'resets_in': limiter.get_reset_time()
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = serializer.save(host=request.user)
        
        response_serializer = QASessionSerializer(session, context={'request': request})
        return Response({
            'data': response_serializer.data,
            'remaining': limiter.get_remaining(),
            'resets_in': limiter.get_reset_time()
        }, status=status.HTTP_201_CREATED)

class QASessionDetailView(generics.RetrieveUpdateDestroyAPIView):
    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAuthenticated()]
        return [AllowAny()]
    
    serializer_class = QASessionSerializer
    lookup_field = 'id'
    lookup_url_kwarg = 'id'
    
    def get_queryset(self):
        return QASession.objects.all()
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def update(self, request, *args, **kwargs):
        session = self.get_object()
        if session.host != request.user:
            return Response(
                {'error': 'You can only update your own Q&A sessions'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)

class QASessionLiveView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        session_id = kwargs.get('id')
        if not session_id:
            return Response(
                {'error': 'Session ID required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            session = QASession.objects.get(id=session_id)
        except QASession.DoesNotExist:
            return Response(
                {'error': 'Session not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        if session.host != request.user:
            return Response(
                {'error': 'You can only control your own sessions'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        is_live = request.data.get('is_live', False)
        session.is_live = is_live
        session.save()
        
        return Response({
            'success': True,
            'is_live': session.is_live
        })

class QAQuestionListView(generics.ListCreateAPIView):
    """List questions or submit a new question with rate limiting"""
    permission_classes = [AllowAny]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return QAQuestionCreateSerializer
        return QAQuestionSerializer
    
    def get_queryset(self):
        session_id = self.request.query_params.get('session_id')
        if not session_id:
            return QAQuestion.objects.none()
        
        return QAQuestion.objects.filter(
            session_id=session_id,
            is_approved=True
        )
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def post(self, request, *args, **kwargs):
        # Get device fingerprint for rate limiting
        device_fingerprint = VoteValidator.get_device_fingerprint(request)
        
        # Rate limiting: 10 questions per hour per device
        limiter = RateLimiter(
            key=f"qa_question_{device_fingerprint}",
            limit=10,
            period=3600  # 1 hour
        )
        
        if not limiter.is_allowed():
            return Response({
                'error': 'Rate limit exceeded. You can only submit 10 questions per hour.',
                'remaining': 0,
                'resets_in': limiter.get_reset_time()
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        session_id = serializer.validated_data['session_id']
        
        try:
            session = QASession.objects.get(id=session_id)
        except QASession.DoesNotExist:
            return Response({
                'error': 'Session not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if session is live
        if not session.is_live:
            return Response({
                'error': 'This Q&A session is not currently live'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if session is full
        if session.questions.count() >= session.max_questions:
            return Response({
                'error': 'This session has reached the maximum number of questions'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        session_id_key = request.session.session_key
        if not session_id_key:
            request.session.create()
            session_id_key = request.session.session_key
        
        question = QAQuestion.objects.create(
            session=session,
            question=serializer.validated_data['question'],
            is_anonymous=True,
            asked_by=None,
            questioner_session=session_id_key,
            is_approved=not session.require_approval
        )
        
        return Response({
            'data': QAQuestionSerializer(question, context={'request': request}).data,
            'remaining': limiter.get_remaining(),
            'resets_in': limiter.get_reset_time()
        }, status=status.HTTP_201_CREATED)

class QAQuestionUpvoteView(generics.CreateAPIView):
    """Upvote a question with rate limiting"""
    permission_classes = [AllowAny]
    
    def post(self, request, pk):
        # Get device fingerprint for rate limiting
        device_fingerprint = VoteValidator.get_device_fingerprint(request)
        
        # Rate limiting: 30 upvotes per minute per device
        limiter = RateLimiter(
            key=f"qa_upvote_{device_fingerprint}",
            limit=30,
            period=60  # 1 minute
        )
        
        if not limiter.is_allowed():
            return Response({
                'error': 'Rate limit exceeded. You can only upvote 30 times per minute.',
                'remaining': 0,
                'resets_in': limiter.get_reset_time()
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        try:
            question = QAQuestion.objects.get(id=pk, is_approved=True)
            
            session_id = request.session.session_key
            if not session_id:
                request.session.create()
                session_id = request.session.session_key
            
            if QAUpvote.objects.filter(question=question, voter_session=session_id).exists():
                return Response({
                    'error': 'You have already upvoted this question'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            QAUpvote.objects.create(
                question=question,
                voter_session=session_id
            )
            
            question.upvotes += 1
            question.save()
            
            return Response({
                'success': True,
                'upvotes': question.upvotes,
                'remaining': limiter.get_remaining(),
                'resets_in': limiter.get_reset_time()
            })
            
        except QAQuestion.DoesNotExist:
            return Response({
                'error': 'Question not found'
            }, status=status.HTTP_404_NOT_FOUND)

class QAQuestionPinView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        try:
            question = QAQuestion.objects.get(id=pk)
            session = question.session
            
            if session.host != request.user:
                return Response(
                    {'error': 'Only the session host can pin questions'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            is_pinned = request.data.get('is_pinned', False)
            question.is_pinned = is_pinned
            question.save()
            
            return Response({
                'success': True,
                'is_pinned': question.is_pinned
            })
        except QAQuestion.DoesNotExist:
            return Response({'error': 'Question not found'}, status=status.HTTP_404_NOT_FOUND)

class QAAnswerView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = QAAnswerCreateSerializer
    
    def post(self, request, *args, **kwargs):
        # Rate limiting: 100 answers per hour per user
        limiter = RateLimiter(
            key=f"qa_answer_{request.user.id}",
            limit=100,
            period=3600  # 1 hour
        )
        
        if not limiter.is_allowed():
            return Response({
                'error': 'Rate limit exceeded. You can only answer 100 questions per hour.',
                'remaining': 0,
                'resets_in': limiter.get_reset_time()
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        question_id = request.data.get('question_id')
        answer_text = request.data.get('answer')
        
        if not question_id or not answer_text:
            return Response(
                {'error': 'question_id and answer are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            question = QAQuestion.objects.get(id=question_id)
            session = question.session
            
            if session.host != request.user:
                return Response(
                    {'error': 'Only the session host can answer questions'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if question.is_answered:
                return Response(
                    {'error': 'This question has already been answered'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            answer = QAAnswer.objects.create(
                question=question,
                answer=answer_text,
                answered_by=request.user
            )
            
            question.is_answered = True
            question.save()
            
            return Response({
                'data': QAAnswerSerializer(answer).data,
                'remaining': limiter.get_remaining(),
                'resets_in': limiter.get_reset_time()
            }, status=status.HTTP_201_CREATED)
            
        except QAQuestion.DoesNotExist:
            return Response({'error': 'Question not found'}, status=status.HTTP_404_NOT_FOUND)


import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings

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
            'message_id': message.id,
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
            # Create the images directory if it doesn't exist
            images_dir = os.path.join(settings.MEDIA_ROOT, 'images')
            if not os.path.exists(images_dir):
                os.makedirs(images_dir, exist_ok=True)
            
            # Save the image file
            import uuid
            file_extension = os.path.splitext(image_file.name)[1]
            file_name = f"image_{uuid.uuid4()}{file_extension}"
            
            # Save file
            saved_path = default_storage.save(f"images/{file_name}", ContentFile(image_file.read()))
            
            # Build the full URL - use the request to build absolute URL
            media_url = f"{settings.MEDIA_URL}{saved_path}"
            
            # Create message with the media URL
            message = AnonymousMessage.objects.create(
                recipient=recipient,
                content="Image message",
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
            print(f"❌ Error saving image: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
class PinMessageView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        try:
            message = AnonymousMessage.objects.get(id=pk, recipient=request.user)
            message.is_pinned = True
            message.save()
            return Response({'success': True, 'is_pinned': True})
        except AnonymousMessage.DoesNotExist:
            return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)


class UnpinMessageView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        try:
            message = AnonymousMessage.objects.get(id=pk, recipient=request.user)
            message.is_pinned = False
            message.save()
            return Response({'success': True, 'is_pinned': False})
        except AnonymousMessage.DoesNotExist:
            return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)