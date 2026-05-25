# backend/anonymous_messages/views.py
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from .models import AnonymousMessage, MessageReport
from .serializers import AnonymousMessageSerializer, SendMessageSerializer, ReportMessageSerializer
from accounts.models import User

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