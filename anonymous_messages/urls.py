# backend/anonymous_messages/urls.py
from django.urls import path
from .views import (
    InboxView, SendMessageView, MessageDetailView, MarkAsReadView, 
    ReportMessageView, StatsView, DeleteMessageView,
    ArchiveMessageView, RestoreMessageView, ArchivedMessagesView, PermanentDeleteView
)

urlpatterns = [
    path('inbox/', InboxView.as_view(), name='inbox'),
    path('send/', SendMessageView.as_view(), name='send-message'),
    path('stats/', StatsView.as_view(), name='stats'),
    path('<int:pk>/', MessageDetailView.as_view(), name='message-detail'),
    path('<int:pk>/read/', MarkAsReadView.as_view(), name='mark-read'),
    path('<int:pk>/report/', ReportMessageView.as_view(), name='report-message'),
    path('<int:pk>/delete/', DeleteMessageView.as_view(), name='delete-message'),
    path('<int:pk>/archive/', ArchiveMessageView.as_view(), name='archive-message'),
    path('<int:pk>/restore/', RestoreMessageView.as_view(), name='restore-message'),
    path('<int:pk>/permanent-delete/', PermanentDeleteView.as_view(), name='permanent-delete'),
    path('archived/', ArchivedMessagesView.as_view(), name='archived-messages'),
]