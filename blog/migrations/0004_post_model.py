"""
Create Post model, migrate existing md files to DB, transition Comment FK.
"""
import os
import re

import yaml
from datetime import datetime, date

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone as tz


def _parse_date_migration(raw_date):
    """다양한 형태의 날짜를 aware datetime으로 변환합니다."""
    if isinstance(raw_date, str):
        try:
            dt = datetime.strptime(raw_date, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                dt = datetime.strptime(raw_date, '%Y-%m-%d')
            except ValueError:
                dt = datetime.now()
    elif isinstance(raw_date, date) and not isinstance(raw_date, datetime):
        dt = datetime(raw_date.year, raw_date.month, raw_date.day)
    elif isinstance(raw_date, datetime):
        dt = raw_date
    else:
        dt = datetime.now()

    if tz.is_naive(dt):
        dt = tz.make_aware(dt)
    return dt


def _parse_tags_migration(raw_tags):
    if isinstance(raw_tags, str):
        return [t.strip() for t in raw_tags.split(',') if t.strip()]
    elif isinstance(raw_tags, list):
        return [str(t).strip() for t in raw_tags if str(t).strip()]
    return []


def _extract_thumbnail(body_md):
    match = re.search(r'!\[[^\]]*\]\(([^)]+)\)', body_md)
    return match.group(1) if match else ''


def _render_md(body_md):
    try:
        import markdown
        import bleach
        html = markdown.markdown(body_md, extensions=['fenced_code', 'tables'])
        allowed_tags = [
            'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'a', 'img', 'ul', 'ol', 'li',
            'code', 'pre', 'blockquote',
            'table', 'thead', 'tbody', 'tr', 'th', 'td',
            'em', 'strong', 'br', 'hr', 'div', 'span',
        ]
        allowed_attrs = {
            'a': ['href', 'title'],
            'img': ['src', 'alt', 'title'],
            'code': ['class'],
        }
        return bleach.clean(html, tags=allowed_tags, attributes=allowed_attrs, protocols=['http', 'https', 'mailto'])
    except ImportError:
        return body_md


def migrate_md_files(apps, schema_editor):
    """posts/*.md 파일을 읽어서 Post 레코드로 생성합니다."""
    Post = apps.get_model('blog', 'Post')
    posts_dir = os.path.join(settings.BASE_DIR, 'posts')

    if not os.path.exists(posts_dir):
        return

    for filename in os.listdir(posts_dir):
        if not filename.endswith('.md'):
            continue

        filepath = os.path.join(posts_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse frontmatter
        meta = {}
        body_md = content
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                meta = yaml.safe_load(parts[1]) or {}
                body_md = parts[2].strip()

        slug = os.path.splitext(filename)[0]
        title = meta.get('title', slug)
        summary = meta.get('summary', '')
        tags = _parse_tags_migration(meta.get('tags', []))
        created_at = _parse_date_migration(meta.get('date', datetime.now()))
        body_html = _render_md(body_md)
        thumbnail_url = _extract_thumbnail(body_md)

        if not Post.objects.filter(slug=slug).exists():
            Post.objects.create(
                title=title,
                slug=slug,
                summary=summary,
                tags=tags,
                body_md=body_md,
                body_html=body_html,
                thumbnail_url=thumbnail_url,
                created_at=created_at,
            )


def link_comments_to_posts(apps, schema_editor):
    """기존 Comment의 post_slug를 Post FK로 연결합니다."""
    Comment = apps.get_model('blog', 'Comment')
    Post = apps.get_model('blog', 'Post')

    for comment in Comment.objects.all():
        try:
            post = Post.objects.get(slug=comment.post_slug)
            comment.post = post
            comment.save(update_fields=['post'])
        except Post.DoesNotExist:
            # 고아 댓글 삭제
            comment.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0003_apikey_hash_storage'),
    ]

    operations = [
        # 1. Post 테이블 생성
        migrations.CreateModel(
            name='Post',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=300)),
                ('slug', models.SlugField(allow_unicode=True, max_length=300, unique=True)),
                ('summary', models.TextField(blank=True, default='')),
                ('tags', models.JSONField(blank=True, default=list)),
                ('body_md', models.TextField()),
                ('body_html', models.TextField(blank=True, default='')),
                ('thumbnail_url', models.CharField(blank=True, default='', max_length=500)),
                ('created_at', models.DateTimeField()),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        # 2. 기존 md 파일 → Post 레코드 생성
        migrations.RunPython(migrate_md_files, migrations.RunPython.noop),
        # 3. Comment에 nullable post FK 추가
        migrations.AddField(
            model_name='comment',
            name='post',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='comments',
                to='blog.post',
            ),
        ),
        # 4. 기존 Comment의 post_slug → Post FK 연결
        migrations.RunPython(link_comments_to_posts, migrations.RunPython.noop),
        # 5. post_slug 필드 제거
        migrations.RemoveField(
            model_name='comment',
            name='post_slug',
        ),
        # 6. post FK를 non-nullable로 변경
        migrations.AlterField(
            model_name='comment',
            name='post',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='comments',
                to='blog.post',
            ),
        ),
    ]
