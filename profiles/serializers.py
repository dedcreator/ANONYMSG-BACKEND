from rest_framework import serializers
from .models import Profile

class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    total_messages = serializers.IntegerField(source='user.total_messages_received', read_only=True)
    custom_css = serializers.CharField(source='user.custom_css', read_only=True)
    profile_theme = serializers.CharField(source='user.profile_theme', read_only=True)
    custom_font = serializers.CharField(source='user.custom_font', read_only=True)
    public_wall = serializers.BooleanField(source='user.public_wall', read_only=True)
    
    class Meta:
        model = Profile
        fields = [
            'username', 'email', 'bio', 'profile_picture', 'banner_image',
            'team_color', 'theme', 'twitter', 'instagram', 'youtube',
            'tiktok', 'github', 'website', 'discord', 'total_messages',
            'custom_css', 'profile_theme', 'custom_font', 'public_wall',
            'created_at', 'updated_at'
        ]

class PublicProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username')
    join_date = serializers.DateTimeField(source='user.date_joined')
    message_count = serializers.IntegerField(source='user.total_messages_received')
    public_wall = serializers.BooleanField(source='user.public_wall')
    allow_gifting = serializers.SerializerMethodField()
    minimum_gift_amount = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    
    class Meta:
        model = Profile
        fields = [
            'username', 'bio', 'profile_picture', 'banner_image',
            'team_color', 'theme', 'twitter', 'instagram', 'youtube',
            'tiktok', 'github', 'website', 'discord',
            'message_count', 'join_date', 'public_wall',
            'allow_gifting', 'minimum_gift_amount', 'currency'
        ]

    def get_allow_gifting(self, obj):
        wallet = getattr(obj.user, 'wallet', None)
        return wallet.allow_gifting if wallet else True

    def get_minimum_gift_amount(self, obj):
        wallet = getattr(obj.user, 'wallet', None)
        return float(wallet.minimum_gift_amount) if wallet else 500.0

    def get_currency(self, obj):
        wallet = getattr(obj.user, 'wallet', None)
        return wallet.currency if wallet else 'NGN'