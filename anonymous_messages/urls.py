# backend/anonymous_messages/urls.py
from django.urls import path
from .views import (
    InboxView, SendMessageView, MessageDetailView, MarkAsReadView, 
    ReportMessageView, StatsView, DeleteMessageView,
    ArchiveMessageView, RestoreMessageView, ArchivedMessagesView, PermanentDeleteView,
    QASessionListView, QASessionDetailView, QASessionLiveView,
    QAQuestionListView, QAQuestionUpvoteView, QAQuestionPinView, QAAnswerView,
    SendVoiceMessageView, SendImageMessageView, PinMessageView, UnpinMessageView,
    ReactMessageView, ReplyMessageView, ToggleWallMessageView, PublicWallView
)

urlpatterns = [
    # Inbox & Message Management
    path('inbox/', InboxView.as_view(), name='inbox'),
    path('send/', SendMessageView.as_view(), name='send-message'),
    path('send-voice/', SendVoiceMessageView.as_view(), name='send-voice'),
    path('send-image/', SendImageMessageView.as_view(), name='send-image'),
    path('stats/', StatsView.as_view(), name='stats'),
    path('wall/<str:username>/', PublicWallView.as_view(), name='public-wall'),
    path('<uuid:pk>/', MessageDetailView.as_view(), name='message-detail'),
    path('<uuid:pk>/read/', MarkAsReadView.as_view(), name='mark-read'),
    path('<uuid:pk>/react/', ReactMessageView.as_view(), name='react-message'),
    path('<uuid:pk>/reply/', ReplyMessageView.as_view(), name='reply-message'),
    path('<uuid:pk>/toggle-wall/', ToggleWallMessageView.as_view(), name='toggle-wall-message'),
    path('<uuid:pk>/report/', ReportMessageView.as_view(), name='report-message'),
    path('<uuid:pk>/delete/', DeleteMessageView.as_view(), name='delete-message'),
    path('<uuid:pk>/archive/', ArchiveMessageView.as_view(), name='archive-message'),
    path('<uuid:pk>/restore/', RestoreMessageView.as_view(), name='restore-message'),
    path('<uuid:pk>/permanent-delete/', PermanentDeleteView.as_view(), name='permanent-delete'),
    path('<uuid:pk>/pin/', PinMessageView.as_view(), name='pin-message'),
    path('<uuid:pk>/unpin/', UnpinMessageView.as_view(), name='unpin-message'),
    path('archived/', ArchivedMessagesView.as_view(), name='archived-messages'),
    
    # Q&A endpoints
    path('qa/sessions/', QASessionListView.as_view(), name='qa-session-list'),
    path('qa/sessions/<uuid:id>/', QASessionDetailView.as_view(), name='qa-session-detail'),
    path('qa/sessions/<uuid:id>/live/', QASessionLiveView.as_view(), name='qa-session-live'),
    path('qa/questions/', QAQuestionListView.as_view(), name='qa-question-list'),
    path('qa/questions/<uuid:pk>/upvote/', QAQuestionUpvoteView.as_view(), name='qa-question-upvote'),
    path('qa/questions/<uuid:pk>/pin/', QAQuestionPinView.as_view(), name='qa-question-pin'),
    path('qa/answers/', QAAnswerView.as_view(), name='qa-answer-create'),
]