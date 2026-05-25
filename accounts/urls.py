from django.urls import path
from .views import ForgotPasswordView, RegisterView, LoginView, CurrentUserView, ResendVerificationEmailView, ResetPasswordView, VerifyEmailView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('me/', CurrentUserView.as_view(), name='me'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('verify/', VerifyEmailView.as_view(), name='verify-email'),
    path('resend-verification/', ResendVerificationEmailView.as_view(), name='resend-verification'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
]
