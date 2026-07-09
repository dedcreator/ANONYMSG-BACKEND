# backend/anonymous_messages/rate_limiter.py
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import hashlib

class RateLimiter:
    """
    Comprehensive rate limiter with device fingerprinting.
    Prevents duplicate voting and limits request frequency.
    """
    
    def __init__(self, key, limit, period, block_duration=None):
        """
        Args:
            key: Unique identifier (IP, user_id, session, etc.)
            limit: Maximum number of actions allowed
            period: Time period in seconds
            block_duration: How long to block after limit is reached (default = period)
        """
        self.key = key
        self.limit = limit
        self.period = period
        self.block_duration = block_duration or period
        
    def is_allowed(self):
        """Check if the action is allowed"""
        # Check if blocked
        block_key = f"blocked_{self.key}"
        if cache.get(block_key):
            return False
        
        # Get current count
        count_key = f"ratelimit_{self.key}"
        current_count = cache.get(count_key, 0)
        
        if current_count >= self.limit:
            # Block for the specified duration
            cache.set(block_key, True, self.block_duration)
            return False
        
        # Increment count
        cache.set(count_key, current_count + 1, self.period)
        return True
    
    def get_remaining(self):
        """Get remaining allowed actions"""
        count_key = f"ratelimit_{self.key}"
        current_count = cache.get(count_key, 0)
        return max(0, self.limit - current_count)
    
    def get_reset_time(self):
        """Get time when rate limit resets"""
        count_key = f"ratelimit_{self.key}"
        current_count = cache.get(count_key, 0)
        if current_count == 0:
            return 0
        ttl = cache.ttl(count_key)
        return ttl if ttl else 0


class VoteValidator:
    """
    Prevents duplicate voting by tracking device fingerprints.
    Uses a combination of IP, session, and browser fingerprint.
    """
    
    @staticmethod
    def get_device_fingerprint(request):
        """
        Generate a unique device fingerprint from:
        - IP Address
        - User Agent
        - Session ID
        - Accept-Language
        """
        ip = request.META.get('REMOTE_ADDR', '')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        session_id = request.session.session_key or ''
        
        # Create fingerprint string
        fingerprint_string = f"{ip}|{user_agent}|{accept_language}|{session_id}"
        
        # Hash to create a consistent identifier
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:32]
    
    @staticmethod
    def has_voted(poll_id, device_fingerprint):
        """Check if a device has already voted on a poll"""
        vote_key = f"poll_vote_{poll_id}_{device_fingerprint}"
        return cache.get(vote_key, False)
    
    @staticmethod
    def record_vote(poll_id, device_fingerprint, duration=86400):
        """
        Record that a device has voted on a poll.
        Default duration: 24 hours
        """
        vote_key = f"poll_vote_{poll_id}_{device_fingerprint}"
        cache.set(vote_key, True, duration)
    
    @staticmethod
    def get_vote_count(poll_id):
        """Get number of unique votes for a poll (from cache)"""
        # This would require tracking all vote keys - not implemented for performance
        # Use database for accurate counts
        pass