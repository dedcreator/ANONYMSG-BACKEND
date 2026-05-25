from rest_framework import serializers
from .models import Profile

class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    total_messages = serializers.IntegerField(source='user.total_messages_received', read_only=True)
    
    class Meta:
        model = Profile
        fields = [
            'username', 'email', 'bio', 'profile_picture', 'banner_image',
            'team_color', 'theme', 'twitter', 'instagram', 'youtube',
            'tiktok', 'github', 'website', 'discord', 'total_messages',
            'created_at', 'updated_at'
        ]

class PublicProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username')
    join_date = serializers.DateTimeField(source='user.date_joined')
    message_count = serializers.IntegerField(source='user.total_messages_received')
    
    class Meta:
        model = Profile
        fields = [
            'username', 'bio', 'profile_picture', 'banner_image',
            'team_color', 'twitter', 'instagram', 'youtube',
            'tiktok', 'github', 'website', 'discord',
            'message_count', 'join_date'
        ]