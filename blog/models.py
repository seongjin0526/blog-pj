from django.conf import settings
from django.db import models


class Comment(models.Model):
    post_slug = models.CharField(max_length=200, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.user} on {self.post_slug}'
