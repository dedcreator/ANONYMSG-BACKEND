# backend/profiles/models.py
from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(max_length=500, blank=True, default='')
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    banner_image = models.ImageField(upload_to='banners/', blank=True, null=True)
    team_color = models.CharField(max_length=7, default='#3B82F6')
    
    THEME_CHOICES = [('dark', 'Dark'), ('light', 'Light'), ('auto', 'Auto')]
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='dark')
    
    twitter = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    youtube = models.URLField(blank=True, null=True)
    tiktok = models.URLField(blank=True, null=True)
    github = models.URLField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    discord = models.URLField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s profile"

# Signal to create profile when user is created
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()