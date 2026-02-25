from django.contrib import admin

from .models import APIKey, Comment


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'scope', 'masked_key', 'is_active', 'is_expired', 'created_at', 'last_used')
    list_filter = ('scope', 'is_active', 'created_at')
    search_fields = ('name', 'user__username')
    readonly_fields = ('key', 'created_at', 'last_used')

    def masked_key(self, obj):
        return obj.masked_key
    masked_key.short_description = 'Key'

    def is_expired(self, obj):
        return obj.is_expired
    is_expired.boolean = True
    is_expired.short_description = '만료'


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'post_slug', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('content', 'post_slug')
