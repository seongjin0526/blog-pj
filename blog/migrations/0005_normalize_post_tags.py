from django.db import migrations


def _normalize_tag(raw_tag):
    return str(raw_tag).strip().lower()


def normalize_post_tags(apps, schema_editor):
    Post = apps.get_model('blog', 'Post')
    for post in Post.objects.only('id', 'tags').iterator():
        raw_tags = post.tags if isinstance(post.tags, list) else []
        normalized = []
        seen = set()
        for raw in raw_tags:
            tag = _normalize_tag(raw)
            if not tag or tag in seen:
                continue
            seen.add(tag)
            normalized.append(tag)
        if normalized != raw_tags:
            Post.objects.filter(pk=post.pk).update(tags=normalized)


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0004_post_model'),
    ]

    operations = [
        migrations.RunPython(normalize_post_tags, migrations.RunPython.noop),
    ]
