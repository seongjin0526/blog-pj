"""Migrate APIKey from plain-text key to SHA-256 hash storage."""

import hashlib

from django.db import migrations, models


def forwards_hash_keys(apps, schema_editor):
    """Hash existing plain-text keys."""
    APIKey = apps.get_model('blog', 'APIKey')
    for api_key in APIKey.objects.all():
        raw_key = api_key.key
        api_key.key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        api_key.key_prefix = raw_key[:8]
        api_key.save(update_fields=['key_hash', 'key_prefix'])


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0002_apikey'),
    ]

    operations = [
        # 1. Add new nullable fields
        migrations.AddField(
            model_name='apikey',
            name='key_hash',
            field=models.CharField(max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='apikey',
            name='key_prefix',
            field=models.CharField(max_length=8, null=True),
        ),
        # 2. Migrate existing data
        migrations.RunPython(forwards_hash_keys, migrations.RunPython.noop),
        # 3. Remove old key field
        migrations.RemoveField(
            model_name='apikey',
            name='key',
        ),
        # 4. Make new fields non-nullable and add indexes
        migrations.AlterField(
            model_name='apikey',
            name='key_hash',
            field=models.CharField(max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name='apikey',
            name='key_prefix',
            field=models.CharField(max_length=8, db_index=True),
        ),
    ]
