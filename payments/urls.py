# backend/payments/urls.py
from django.urls import path
from .views import (
    InitializeGiftPaymentView,
    InitializeQAPassPaymentView,
    VerifyPaymentView,
    FlutterwaveWebhookView,
    CreatorWalletView,
    CreatorTransactionsListView,
    CreatorGiftsListView,
    CreatorLeaderboardView,
    BankListView,
    ResolveAccountView,
    RequestPayoutView,
    CheckQASessionAccessView
)

urlpatterns = [
    path('initialize-gift/', InitializeGiftPaymentView.as_view(), name='initialize-gift'),
    path('initialize-qa-pass/', InitializeQAPassPaymentView.as_view(), name='initialize-qa-pass'),
    path('verify/', VerifyPaymentView.as_view(), name='verify-payment'),
    path('webhook/', FlutterwaveWebhookView.as_view(), name='flutterwave-webhook'),
    path('wallet/', CreatorWalletView.as_view(), name='creator-wallet'),
    path('transactions/', CreatorTransactionsListView.as_view(), name='creator-transactions'),
    path('gifts/', CreatorGiftsListView.as_view(), name='creator-gifts'),
    path('leaderboard/<str:username>/', CreatorLeaderboardView.as_view(), name='creator-leaderboard'),
    path('banks/', BankListView.as_view(), name='supported-banks'),
    path('resolve-account/', ResolveAccountView.as_view(), name='resolve-account'),
    path('request-payout/', RequestPayoutView.as_view(), name='request-payout'),
    path('qa-access/<uuid:session_id>/', CheckQASessionAccessView.as_view(), name='qa-access-check'),
]
