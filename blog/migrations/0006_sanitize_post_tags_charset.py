import re

from django.db import migrations


TAG_RE = re.compile(r'^[a-z가-힣]+$')


def sanitize_post_tags(apps, schema_editor):
    Post = apps.get_model('blog', 'Post')
    for post in Post.objects.only('id', 'tags').iterator():
        raw_tags = post.tags if isinstance(post.tags, list) else []
        normalized = []
        seen = set()
        for raw in raw_tags:
            tag = str(raw).strip().lower()
            if not tag or not TAG_RE.fullmatch(tag) or tag in seen:
                continue
            seen.add(tag)
            normalized.append(tag)
        if normalized != raw_tags:
            Post.objects.filter(pk=post.pk).update(tags=normalized)


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0005_normalize_post_tags'),
    ]

    operations = [
        migrations.RunPython(sanitize_post_tags, migrations.RunPython.noop),
    ]
