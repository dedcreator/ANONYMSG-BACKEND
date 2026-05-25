# backend/accounts/views.py
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
from datetime import timedelta
from .serializers import RegisterSerializer, LoginSerializer, UserSerializer
from .models import User
from .utils import send_verification_email, send_password_reset_email

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Send verification email
        send_verification_email(user)
        
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
        
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        try:
            user = User.objects.get(email=email)
            user = authenticate(username=user.username, password=password)
        except User.DoesNotExist:
            user = None
        
        if not user:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        
        if not user.is_verified:
            return Response({'error': 'Please verify your email first'}, status=status.HTTP_401_UNAUTHORIZED)
        
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })
class CurrentUserView(generics.RetrieveUpdateAPIView):  # Change this line
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    
    def get_object(self):
        return self.request.user
    
    def patch(self, request, *args, **kwargs):
        """Handle partial updates for username and email"""
        user = self.get_object()
        serializer = self.get_serializer(user, data=request.data, partial=True)
        
        if serializer.is_valid():
            # Check if username is taken
            new_username = request.data.get('username')
            if new_username and new_username != user.username:
                if User.objects.filter(username=new_username).exists():
                    return Response({'error': 'Username already taken'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if email is taken
            new_email = request.data.get('email')
            if new_email and new_email != user.email:
                if User.objects.filter(email=new_email).exists():
                    return Response({'error': 'Email already taken'}, status=status.HTTP_400_BAD_REQUEST)
            
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class VerifyEmailView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        token = request.data.get('token')
        email = request.data.get('email')
        
        if not token or not email:
            return Response({'error': 'Token and email are required'}, status=400)
        
        try:
            user = User.objects.get(email=email, verification_token=token)
            
            # Check if token expired (24 hours)
            if user.verification_token_created_at < timezone.now() - timedelta(hours=24):
                # Generate new token
                send_verification_email(user)
                return Response({'error': 'Token expired. A new verification email has been sent.'}, status=400)
            
            user.is_verified = True
            user.verification_token = None
            user.verification_token_created_at = None
            user.save()
            
            return Response({'message': 'Email verified successfully!'})
        except User.DoesNotExist:
            return Response({'error': 'Invalid verification link'}, status=400)

class ResendVerificationEmailView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response({'error': 'Email is required'}, status=400)
        
        try:
            user = User.objects.get(email=email)
            
            if user.is_verified:
                return Response({'error': 'Email already verified'}, status=400)
            
            send_verification_email(user)
            return Response({'message': 'Verification email sent!'})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)

class ForgotPasswordView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response({'error': 'Email is required'}, status=400)
        
        try:
            user = User.objects.get(email=email)
            send_password_reset_email(user)
            return Response({'message': 'Password reset email sent! Check your inbox.'})
        except User.DoesNotExist:
            # Don't reveal that user doesn't exist for security
            return Response({'message': 'If an account exists with this email, a reset link has been sent.'})

class ResetPasswordView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        token = request.data.get('token')
        email = request.data.get('email')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')
        
        if not all([token, email, new_password, confirm_password]):
            return Response({'error': 'All fields are required'}, status=400)
        
        if new_password != confirm_password:
            return Response({'error': 'Passwords do not match'}, status=400)
        
        if len(new_password) < 6:
            return Response({'error': 'Password must be at least 6 characters'}, status=400)
        
        try:
            user = User.objects.get(email=email, reset_password_token=token)
            
            # Check if token expired (1 hour)
            if user.reset_password_token_created_at < timezone.now() - timedelta(hours=1):
                return Response({'error': 'Reset link expired. Please request a new one.'}, status=400)
            
            user.set_password(new_password)
            user.reset_password_token = None
            user.reset_password_token_created_at = None
            user.save()
            
            return Response({'message': 'Password reset successfully! You can now login.'})
        except User.DoesNotExist:
            return Response({'error': 'Invalid reset link'}, status=400)

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

class ResendVerificationEmailView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response({'error': 'Email is required'}, status=400)
        
        try:
            user = User.objects.get(email=email)
            
            if user.is_verified:
                return Response({'error': 'Email already verified'}, status=400)
            
            send_verification_email(user)
            return Response({'message': 'Verification email sent!'})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)