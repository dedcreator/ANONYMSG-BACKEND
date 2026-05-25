from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import NotFound
from .models import Profile
from .serializers import ProfileSerializer, PublicProfileSerializer
from accounts.models import User

class ProfileDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProfileSerializer
    
    def get_object(self):
        return self.request.user.profile

class PublicProfileView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicProfileSerializer
    
    def get_object(self):
        username = self.kwargs['username']
        try:
            user = User.objects.get(username=username)
            return user.profile
        except User.DoesNotExist:
            raise NotFound("User not found")