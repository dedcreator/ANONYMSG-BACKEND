# backend/create_test_user.py
import os
import django
import sys

# Set up Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anonmsg_backend.settings')
django.setup()

from accounts.models import User
from profiles.models import Profile

def create_test_user():
    username = "testuser"
    email = "test@example.com"
    password = "testpass123"
    
    # Check if user already exists
    if User.objects.filter(username=username).exists():
        print(f"User '{username}' already exists!")
        return
    
    # Create user
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password
    )
    user.is_verified = True
    user.save()
    
    # Create profile
    profile, created = Profile.objects.get_or_create(user=user)
    profile.bio = "This is a test user account. Send me anonymous messages!"
    profile.team_color = "#3B82F6"
    profile.save()
    
    print(f"✅ Test user created successfully!")
    print(f"   Username: {username}")
    print(f"   Email: {email}")
    print(f"   Password: {password}")
    print(f"   Profile URL: /@{username}")

def create_multiple_test_users():
    """Create multiple test users for testing"""
    users = [
        {"username": "alice", "email": "alice@example.com", "bio": "Artist & Creator"},
        {"username": "bob", "email": "bob@example.com", "bio": "Tech Enthusiast"},
        {"username": "charlie", "email": "charlie@example.com", "bio": "Writer & Storyteller"},
        {"username": "diana", "email": "diana@example.com", "bio": "Musician"},
        {"username": "eve", "email": "eve@example.com", "bio": "Designer"},
    ]
    
    for user_data in users:
        if not User.objects.filter(username=user_data["username"]).exists():
            user = User.objects.create_user(
                username=user_data["username"],
                email=user_data["email"],
                password="testpass123"
            )
            user.is_verified = True
            user.save()
            
            profile, created = Profile.objects.get_or_create(user=user)
            profile.bio = user_data["bio"]
            profile.save()
            
            print(f"✅ Created: {user_data['username']} / testpass123")
        else:
            print(f"⏭️ Skipped: {user_data['username']} (already exists)")

if __name__ == "__main__":
    print("=" * 50)
    print("Create Test User")
    print("=" * 50)
    
    # Create single test user
    create_test_user()
    
    print("\n" + "-" * 50)
    print("Create multiple test users? (y/n)")
    
    # Uncomment to create multiple users
    # create_multiple_test_users()