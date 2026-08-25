# backend/accounts/views.py
import logging
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
from datetime import timedelta
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer,
    ForgotPasswordSerializer, ResetPasswordSerializer
)
from .models import User
from .utils import send_verification_email, send_password_reset_email

logger = logging.getLogger(__name__)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Send verification email
        try:
            send_verification_email(user)
        except Exception as e:
            logger.error(f"Error sending verification email during registration: {e}")

        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'message': 'Please check your email to verify your account'
        }, status=status.HTTP_201_CREATED)


class LoginView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].strip().lower()
        password = serializer.validated_data['password']
        
        user_obj = User.objects.filter(email__iexact=email).first()
        user = None
        if user_obj:
            user = authenticate(username=user_obj.username, password=password)

        if not user:
            return Response({
                'error': 'Invalid credentials',
                'detail': 'The email or password you entered is incorrect.'
            }, status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_200_OK)


class CurrentUserView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class VerifyEmailView(generics.GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token', '').strip()
        email = request.data.get('email', '').strip().lower()

        if not token or not email:
            return Response({'error': 'Token and email are required'}, status=400)

        try:
            user = User.objects.filter(email__iexact=email, verification_token=token).first()
            if not user:
                return Response({'error': 'Invalid verification link'}, status=400)

            # Check if token expired (24 hours)
            if user.verification_token_created_at and user.verification_token_created_at < timezone.now() - timedelta(hours=24):
                send_verification_email(user)
                return Response({'error': 'Token expired. A new verification email has been sent.'}, status=400)

            user.is_verified = True
            user.verification_token = None
            user.verification_token_created_at = None
            user.save()

            return Response({'message': 'Email verified successfully!'})
        except Exception as e:
            logger.error(f"Error verifying email: {e}")
            return Response({'error': 'Invalid verification link'}, status=400)


class ResendVerificationEmailView(generics.GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()

        if not email:
            return Response({'error': 'Email is required'}, status=400)

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response({'error': 'User not found'}, status=404)

        if user.is_verified:
            return Response({'error': 'Email already verified'}, status=400)

        send_verification_email(user)
        return Response({'message': 'Verification email sent!'})


class ForgotPasswordView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ForgotPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].strip().lower()
        logger.info(f"Password reset requested for email: {email}")

        user = User.objects.filter(email__iexact=email).first()
        if user:
            logger.info(f"User found for password reset: {user.username} ({user.email}). Sending reset email...")
            sent = send_password_reset_email(user)
            if sent:
                logger.info(f"Password reset email sent successfully to {user.email}")
            else:
                logger.error(f"Failed to dispatch password reset email to {user.email}")
        else:
            logger.warning(f"Password reset attempted for non-existent email: {email}")

        return Response({'message': 'If an account exists with this email, a reset link has been sent.'})


class ResetPasswordView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['token'].strip()
        email = serializer.validated_data['email'].strip().lower()
        new_password = serializer.validated_data['new_password']

        user = User.objects.filter(email__iexact=email, reset_password_token=token).first()
        if not user:
            return Response({'error': 'Invalid or expired reset link. Please request a new one.'}, status=400)

        # Check if token expired (1 hour)
        if not user.reset_password_token_created_at or user.reset_password_token_created_at < timezone.now() - timedelta(hours=1):
            return Response({'error': 'Reset link expired. Please request a new one.'}, status=400)

        user.set_password(new_password)
        user.reset_password_token = None
        user.reset_password_token_created_at = None
        user.save()

        logger.info(f"Password successfully reset for user: {user.username}")
        return Response({'message': 'Password reset successfully! You can now login.'})


class UserSettingsView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            'email_notifications': user.email_notifications,
            'push_notifications': user.push_notifications,
            'weekly_digest': user.weekly_digest,
            'public_wall': user.public_wall,
            'allow_voice': user.allow_voice,
            'auto_delete': user.auto_delete,
        })

    def patch(self, request):
        user = request.user
        user.email_notifications = request.data.get('email_notifications', user.email_notifications)
        user.push_notifications = request.data.get('push_notifications', user.push_notifications)
        user.weekly_digest = request.data.get('weekly_digest', user.weekly_digest)
        user.public_wall = request.data.get('public_wall', user.public_wall)
        user.allow_voice = request.data.get('allow_voice', user.allow_voice)
        user.auto_delete = request.data.get('auto_delete', user.auto_delete)
        user.save()
        return Response({'message': 'Settings updated'})

