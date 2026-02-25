import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_api_key():
    return secrets.token_urlsafe(36)


class APIKey(models.Model):
    SCOPE_CHOICES = [
        ('read', 'Read'),
        ('write', 'Write'),
        ('admin', 'Admin'),
    ]
    SCOPE_HIERARCHY = {'read': 0, 'write': 1, 'admin': 2}

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_keys')
    key = models.CharField(max_length=64, unique=True, default=generate_api_key)
    name = models.CharField(max_length=100)
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default='read')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.user})'

    @property
    def is_expired(self):
        if self.expires_at is None:
            return False
        return timezone.now() >= self.expires_at

    @property
    def is_valid(self):
        return self.is_active and not self.is_expired and self.user.is_active

    @property
    def masked_key(self):
        if len(self.key) > 12:
            return self.key[:8] + '...' + self.key[-4:]
        return self.key

    def has_scope(self, required_scope):
        return self.SCOPE_HIERARCHY.get(self.scope, 0) >= self.SCOPE_HIERARCHY.get(required_scope, 0)


class Comment(models.Model):
    post_slug = models.CharField(max_length=200, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.user} on {self.post_slug}'
