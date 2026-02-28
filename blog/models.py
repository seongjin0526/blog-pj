import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_api_key():
    return secrets.token_urlsafe(36)


class Post(models.Model):
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True, allow_unicode=True)
    summary = models.TextField(blank=True, default='')
    tags = models.JSONField(default=list, blank=True)
    body_md = models.TextField()
    search_document = models.TextField(blank=True, default='')
    body_html = models.TextField(blank=True, default='')
    thumbnail_url = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, **kwargs):
        from .utils import render_markdown, extract_thumbnail_url, generate_thumbnail, normalize_tags
        self.tags = normalize_tags(self.tags)
        # 검색 성능을 위해 조회 대상 텍스트를 별도 컬럼으로 유지
        self.search_document = '\n'.join([
            self.title or '',
            self.summary or '',
            self.body_md or '',
        ])
        if self.body_md:
            self.body_html = render_markdown(self.body_md)
            original_url = extract_thumbnail_url(self.body_md)
            self.thumbnail_url = generate_thumbnail(original_url) if original_url else ''
        super().save(**kwargs)


class APIKey(models.Model):
    SCOPE_CHOICES = [
        ('read', 'Read'),
        ('write', 'Write'),
        ('admin', 'Admin'),
    ]
    SCOPE_HIERARCHY = {'read': 0, 'write': 1, 'admin': 2}

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_keys')
    key_hash = models.CharField(max_length=64, unique=True)
    key_prefix = models.CharField(max_length=8, db_index=True)
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

    def set_key(self, raw_key):
        """평문 키를 받아 해시와 prefix를 저장합니다."""
        self.key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        self.key_prefix = raw_key[:8]

    @classmethod
    def check_key(cls, raw_key):
        """평문 키로 APIKey를 조회합니다. 없으면 None을 반환합니다."""
        prefix = raw_key[:8]
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        try:
            return cls.objects.select_related('user').get(
                key_prefix=prefix,
                key_hash=key_hash,
            )
        except cls.DoesNotExist:
            return None

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
        return self.key_prefix + '...'

    def has_scope(self, required_scope):
        return self.SCOPE_HIERARCHY.get(self.scope, 0) >= self.SCOPE_HIERARCHY.get(required_scope, 0)


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.user} on {self.post.slug}'
