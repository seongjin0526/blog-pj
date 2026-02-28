from django.db import migrations, models


def populate_search_document(apps, schema_editor):
    Post = apps.get_model('blog', 'Post')
    for post in Post.objects.only('id', 'title', 'summary', 'body_md').iterator():
        doc = '\n'.join([
            post.title or '',
            post.summary or '',
            post.body_md or '',
        ])
        Post.objects.filter(pk=post.pk).update(search_document=doc)


def create_postgres_search_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return

    schema_editor.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm;')
    schema_editor.execute(
        'CREATE INDEX IF NOT EXISTS blog_post_search_document_trgm_idx '
        'ON blog_post USING GIN (search_document gin_trgm_ops);'
    )
    schema_editor.execute(
        "CREATE INDEX IF NOT EXISTS blog_post_search_document_fts_idx "
        "ON blog_post USING GIN (to_tsvector('simple', search_document));"
    )
    schema_editor.execute(
        'CREATE INDEX IF NOT EXISTS blog_post_tags_gin_idx '
        'ON blog_post USING GIN (tags);'
    )


def drop_postgres_search_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return

    schema_editor.execute('DROP INDEX IF EXISTS blog_post_tags_gin_idx;')
    schema_editor.execute('DROP INDEX IF EXISTS blog_post_search_document_fts_idx;')
    schema_editor.execute('DROP INDEX IF EXISTS blog_post_search_document_trgm_idx;')


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0006_sanitize_post_tags_charset'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='search_document',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.RunPython(populate_search_document, migrations.RunPython.noop),
        migrations.RunPython(create_postgres_search_indexes, drop_postgres_search_indexes),
    ]
