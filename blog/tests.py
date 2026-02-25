import io
import json
import os
import shutil
import tempfile
import zipfile
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from blog import utils
from blog.models import APIKey, Comment


# 테스트용 임시 디렉토리를 사용하여 실제 posts/media를 오염시키지 않음
TEST_POSTS_DIR = tempfile.mkdtemp(prefix='test_posts_')
TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix='test_media_')


def _patch_posts_dir(new_dir):
    """utils.POSTS_DIR을 임시 디렉토리로 교체합니다."""
    utils.POSTS_DIR = new_dir


# ──────────────────────────────────────────────
# 단위 테스트: utils 함수
# ──────────────────────────────────────────────

class MakeSlugTest(TestCase):
    def test_basic(self):
        self.assertEqual(utils.make_slug('Hello World'), 'hello-world')

    def test_korean(self):
        self.assertEqual(utils.make_slug('파이썬 튜토리얼'), '파이썬-튜토리얼')

    def test_special_chars(self):
        self.assertEqual(utils.make_slug('Hello! @World#'), 'hello-world')

    def test_empty(self):
        self.assertEqual(utils.make_slug(''), 'untitled')
        self.assertEqual(utils.make_slug('!!!'), 'untitled')


class ExtractFrontmatterTest(TestCase):
    def test_with_frontmatter(self):
        content = "---\ntitle: Test\ndate: 2025-01-01\n---\n\nHello body"
        meta, body = utils.extract_frontmatter_and_body(content)
        self.assertEqual(meta['title'], 'Test')
        self.assertEqual(body, 'Hello body')

    def test_without_frontmatter(self):
        content = "Just plain markdown content"
        meta, body = utils.extract_frontmatter_and_body(content)
        self.assertEqual(meta, {})
        self.assertEqual(body, content)

    def test_partial_frontmatter(self):
        content = "---\ntitle: Only Title\n---\n\nBody here"
        meta, body = utils.extract_frontmatter_and_body(content)
        self.assertEqual(meta['title'], 'Only Title')
        self.assertNotIn('date', meta)
        self.assertEqual(body, 'Body here')


class EnsureFrontmatterTest(TestCase):
    def test_fills_missing_title(self):
        meta = {}
        result = utils.ensure_frontmatter(meta, 'fallback-name')
        self.assertEqual(result['title'], 'fallback-name')
        self.assertIn('date', result)

    def test_preserves_existing(self):
        meta = {'title': 'My Title', 'date': '2025-06-01'}
        result = utils.ensure_frontmatter(meta, 'fallback')
        self.assertEqual(result['title'], 'My Title')
        self.assertEqual(result['date'], '2025-06-01')


class RebuildMdContentTest(TestCase):
    def test_basic(self):
        meta = {'title': 'Test Post', 'date': '2025-01-01', 'summary': 'A test', 'tags': ['python', 'django']}
        body = 'Hello world'
        result = utils.rebuild_md_content(meta, body)
        self.assertIn('title: Test Post', result)
        self.assertIn('date: 2025-01-01', result)
        self.assertIn('tags: [python, django]', result)
        self.assertIn('Hello world', result)

    def test_empty_tags(self):
        meta = {'title': 'No Tags', 'date': '2025-01-01'}
        result = utils.rebuild_md_content(meta, 'body')
        self.assertIn('tags: []', result)


class RewriteImagePathsTest(TestCase):
    def test_basic_rewrite(self):
        body = '![alt](images/photo.png)'
        mapping = {'images/photo.png': '/media/uploads/abc123.png'}
        result = utils.rewrite_image_paths(body, mapping)
        self.assertEqual(result, '![alt](/media/uploads/abc123.png)')

    def test_basename_fallback(self):
        body = '![alt](./subdir/photo.png)'
        mapping = {'photo.png': '/media/uploads/abc123.png'}
        result = utils.rewrite_image_paths(body, mapping)
        self.assertEqual(result, '![alt](/media/uploads/abc123.png)')

    def test_http_url_skipped(self):
        body = '![alt](https://example.com/photo.png)'
        mapping = {'photo.png': '/media/uploads/abc123.png'}
        result = utils.rewrite_image_paths(body, mapping)
        self.assertEqual(result, '![alt](https://example.com/photo.png)')

    def test_no_match_unchanged(self):
        body = '![alt](unknown.png)'
        mapping = {'other.png': '/media/uploads/abc.png'}
        result = utils.rewrite_image_paths(body, mapping)
        self.assertEqual(result, '![alt](unknown.png)')


class ValidateZipSafetyTest(TestCase):
    def _make_zip(self, file_map):
        """file_map = {name: content_bytes}로 in-memory zip을 만듭니다."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            for name, data in file_map.items():
                zf.writestr(name, data)
        buf.seek(0)
        return zipfile.ZipFile(buf)

    def test_valid_zip(self):
        zf = self._make_zip({'post.md': b'# Hello', 'img.png': b'\x89PNG'})
        self.assertIsNone(utils.validate_zip_safety(zf))

    def test_no_md_file(self):
        zf = self._make_zip({'img.png': b'\x89PNG'})
        err = utils.validate_zip_safety(zf)
        self.assertIn('.md 파일이 없습니다', err)

    def test_multiple_md_files(self):
        zf = self._make_zip({'a.md': b'# A', 'b.md': b'# B'})
        err = utils.validate_zip_safety(zf)
        self.assertIn('2개', err)

    def test_path_traversal(self):
        zf = self._make_zip({'../evil.md': b'# Evil'})
        err = utils.validate_zip_safety(zf)
        self.assertIn('허용되지 않는 경로', err)

    def test_macosx_skipped(self):
        # __MACOSX/post.md는 무시되어야 하므로 유효한 .md가 0개
        zf = self._make_zip({'__MACOSX/post.md': b'# Skip', 'real.md': b'# Real'})
        self.assertIsNone(utils.validate_zip_safety(zf))


class IsValidEntryTest(TestCase):
    def test_normal_file(self):
        self.assertTrue(utils._is_valid_entry('post.md'))
        self.assertTrue(utils._is_valid_entry('images/photo.png'))

    def test_macosx(self):
        self.assertFalse(utils._is_valid_entry('__MACOSX/._post.md'))

    def test_ds_store(self):
        self.assertFalse(utils._is_valid_entry('.DS_Store'))

    def test_hidden_file(self):
        self.assertFalse(utils._is_valid_entry('.hidden'))


# ──────────────────────────────────────────────
# 통합 테스트: process_uploaded_md / process_uploaded_zip
# ──────────────────────────────────────────────

@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ProcessUploadedMdTest(TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix='test_posts_md_')
        self._orig = utils.POSTS_DIR
        _patch_posts_dir(self.test_dir)

    def tearDown(self):
        _patch_posts_dir(self._orig)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_md_with_frontmatter(self):
        content = "---\ntitle: My Post\ndate: 2025-06-15\ntags: [python]\n---\n\n본문입니다."
        f = SimpleUploadedFile('my-post.md', content.encode('utf-8'))
        slug, error = utils.process_uploaded_md(f)
        self.assertIsNone(error)
        self.assertEqual(slug, 'my-post')
        filepath = os.path.join(self.test_dir, f'{slug}.md')
        self.assertTrue(os.path.exists(filepath))
        with open(filepath, 'r') as fh:
            saved = fh.read()
        self.assertIn('title: My Post', saved)
        self.assertIn('본문입니다.', saved)

    def test_md_without_frontmatter(self):
        content = "# Just a heading\n\nSome content here."
        f = SimpleUploadedFile('my-article.md', content.encode('utf-8'))
        slug, error = utils.process_uploaded_md(f)
        self.assertIsNone(error)
        self.assertIn('my-article', slug)
        filepath = os.path.join(self.test_dir, f'{slug}.md')
        with open(filepath, 'r') as fh:
            saved = fh.read()
        self.assertIn('title: my-article', saved)
        self.assertIn('date:', saved)

    def test_md_non_utf8(self):
        # EUC-KR 인코딩 텍스트 - UTF-8 디코딩 시 에러
        f = SimpleUploadedFile('bad.md', '한글테스트'.encode('euc-kr'))
        slug, error = utils.process_uploaded_md(f)
        self.assertIsNone(slug)
        self.assertIn('UTF-8', error)

    def test_slug_collision(self):
        content = "---\ntitle: Duplicate\n---\n\nBody"
        f1 = SimpleUploadedFile('dup.md', content.encode('utf-8'))
        slug1, _ = utils.process_uploaded_md(f1)

        f2 = SimpleUploadedFile('dup.md', content.encode('utf-8'))
        slug2, _ = utils.process_uploaded_md(f2)

        self.assertNotEqual(slug1, slug2)
        self.assertTrue(slug2.endswith('-1'))


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ProcessUploadedZipTest(TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix='test_posts_zip_')
        self._orig = utils.POSTS_DIR
        _patch_posts_dir(self.test_dir)
        self.media_uploads = os.path.join(TEST_MEDIA_ROOT, 'uploads')
        os.makedirs(self.media_uploads, exist_ok=True)

    def tearDown(self):
        _patch_posts_dir(self._orig)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _make_zip_file(self, file_map):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            for name, data in file_map.items():
                zf.writestr(name, data)
        buf.seek(0)
        return SimpleUploadedFile('test.zip', buf.read(), content_type='application/zip')

    def test_zip_with_md_and_images(self):
        md_content = "---\ntitle: Zip Post\ntags: [test]\n---\n\n![photo](images/photo.png)\n"
        f = self._make_zip_file({
            'post.md': md_content.encode('utf-8'),
            'images/photo.png': b'\x89PNG fake image data',
        })
        slug, error = utils.process_uploaded_zip(f)
        self.assertIsNone(error)
        self.assertEqual(slug, 'zip-post')
        filepath = os.path.join(self.test_dir, f'{slug}.md')
        with open(filepath, 'r') as fh:
            saved = fh.read()
        self.assertIn('title: Zip Post', saved)
        # 이미지 경로가 /media/uploads/로 치환되었는지 확인
        self.assertIn('/media/uploads/', saved)
        self.assertNotIn('images/photo.png', saved)

    def test_zip_md_only(self):
        md_content = "---\ntitle: No Images\n---\n\nJust text."
        f = self._make_zip_file({'article.md': md_content.encode('utf-8')})
        slug, error = utils.process_uploaded_zip(f)
        self.assertIsNone(error)
        self.assertEqual(slug, 'no-images')

    def test_zip_no_md(self):
        f = self._make_zip_file({'img.png': b'\x89PNG'})
        slug, error = utils.process_uploaded_zip(f)
        self.assertIsNone(slug)
        self.assertIn('.md 파일이 없습니다', error)

    def test_zip_multiple_md(self):
        f = self._make_zip_file({'a.md': b'# A', 'b.md': b'# B'})
        slug, error = utils.process_uploaded_zip(f)
        self.assertIsNone(slug)
        self.assertIn('2개', error)

    def test_zip_path_traversal(self):
        f = self._make_zip_file({'../evil.md': b'# Evil'})
        slug, error = utils.process_uploaded_zip(f)
        self.assertIsNone(slug)
        self.assertIn('허용되지 않는 경로', error)

    def test_zip_macosx_ignored(self):
        md_content = "---\ntitle: Real Post\n---\n\nBody"
        f = self._make_zip_file({
            'post.md': md_content.encode('utf-8'),
            '__MACOSX/._post.md': b'junk',
            '.DS_Store': b'junk',
        })
        slug, error = utils.process_uploaded_zip(f)
        self.assertIsNone(error)
        self.assertEqual(slug, 'real-post')

    def test_invalid_zip(self):
        f = SimpleUploadedFile('bad.zip', b'this is not a zip', content_type='application/zip')
        slug, error = utils.process_uploaded_zip(f)
        self.assertIsNone(slug)
        self.assertIn('유효하지 않은 ZIP', error)

    def test_zip_non_utf8_md(self):
        f = self._make_zip_file({'post.md': '한글'.encode('euc-kr')})
        slug, error = utils.process_uploaded_zip(f)
        self.assertIsNone(slug)
        self.assertIn('UTF-8', error)


# ──────────────────────────────────────────────
# 뷰 통합 테스트: post_upload 엔드포인트
# ──────────────────────────────────────────────

@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class PostUploadViewTest(TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix='test_posts_view_')
        self._orig = utils.POSTS_DIR
        _patch_posts_dir(self.test_dir)
        self.staff = User.objects.create_user('admin', password='pass', is_staff=True)
        self.normal = User.objects.create_user('user', password='pass', is_staff=False)

    def tearDown(self):
        _patch_posts_dir(self._orig)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _make_zip_bytes(self, file_map):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            for name, data in file_map.items():
                zf.writestr(name, data)
        return buf.getvalue()

    def test_staff_upload_md(self):
        self.client.login(username='admin', password='pass')
        content = "---\ntitle: View Test\n---\n\nBody"
        f = SimpleUploadedFile('test.md', content.encode('utf-8'))
        resp = self.client.post('/upload-post/', {'file': f})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('url', data)
        self.assertIn('/post/', data['url'])

    def test_staff_upload_zip(self):
        self.client.login(username='admin', password='pass')
        md_content = "---\ntitle: Zip View\n---\n\nBody"
        zip_bytes = self._make_zip_bytes({'post.md': md_content.encode('utf-8')})
        f = SimpleUploadedFile('test.zip', zip_bytes, content_type='application/zip')
        resp = self.client.post('/upload-post/', {'file': f})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('url', data)

    def test_non_staff_blocked(self):
        self.client.login(username='user', password='pass')
        f = SimpleUploadedFile('test.md', b'# Hello')
        resp = self.client.post('/upload-post/', {'file': f})
        # staff_member_required는 login 페이지로 리다이렉트
        self.assertEqual(resp.status_code, 302)

    def test_anonymous_blocked(self):
        f = SimpleUploadedFile('test.md', b'# Hello')
        resp = self.client.post('/upload-post/', {'file': f})
        self.assertEqual(resp.status_code, 302)

    def test_no_file(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.post('/upload-post/', {})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.json())

    def test_invalid_extension(self):
        self.client.login(username='admin', password='pass')
        f = SimpleUploadedFile('test.txt', b'Hello')
        resp = self.client.post('/upload-post/', {'file': f})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('.md 또는 .zip', resp.json()['error'])

    def test_get_method_not_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get('/upload-post/')
        self.assertEqual(resp.status_code, 405)


# ──────────────────────────────────────────────
# APIKey 모델 테스트
# ──────────────────────────────────────────────

class APIKeyModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', password='pass')

    def test_key_auto_generated(self):
        key = APIKey.objects.create(user=self.user, name='test')
        self.assertTrue(len(key.key) > 20)

    def test_is_expired_no_expiry(self):
        key = APIKey.objects.create(user=self.user, name='test')
        self.assertFalse(key.is_expired)

    def test_is_expired_future(self):
        key = APIKey.objects.create(user=self.user, name='test', expires_at=timezone.now() + timedelta(days=30))
        self.assertFalse(key.is_expired)

    def test_is_expired_past(self):
        key = APIKey.objects.create(user=self.user, name='test', expires_at=timezone.now() - timedelta(seconds=1))
        self.assertTrue(key.is_expired)

    def test_is_valid(self):
        key = APIKey.objects.create(user=self.user, name='test')
        self.assertTrue(key.is_valid)

    def test_is_valid_inactive(self):
        key = APIKey.objects.create(user=self.user, name='test', is_active=False)
        self.assertFalse(key.is_valid)

    def test_is_valid_expired(self):
        key = APIKey.objects.create(user=self.user, name='test', expires_at=timezone.now() - timedelta(seconds=1))
        self.assertFalse(key.is_valid)

    def test_is_valid_inactive_user(self):
        self.user.is_active = False
        self.user.save()
        key = APIKey.objects.create(user=self.user, name='test')
        self.assertFalse(key.is_valid)

    def test_masked_key(self):
        key = APIKey.objects.create(user=self.user, name='test')
        masked = key.masked_key
        self.assertTrue(masked.startswith(key.key[:8]))
        self.assertTrue(masked.endswith(key.key[-4:]))
        self.assertIn('...', masked)

    def test_has_scope_hierarchy(self):
        key = APIKey.objects.create(user=self.user, name='test', scope='admin')
        self.assertTrue(key.has_scope('read'))
        self.assertTrue(key.has_scope('write'))
        self.assertTrue(key.has_scope('admin'))

    def test_scope_write_cannot_admin(self):
        key = APIKey.objects.create(user=self.user, name='test', scope='write')
        self.assertTrue(key.has_scope('read'))
        self.assertTrue(key.has_scope('write'))
        self.assertFalse(key.has_scope('admin'))

    def test_scope_read_only(self):
        key = APIKey.objects.create(user=self.user, name='test', scope='read')
        self.assertTrue(key.has_scope('read'))
        self.assertFalse(key.has_scope('write'))
        self.assertFalse(key.has_scope('admin'))


# ──────────────────────────────────────────────
# 데코레이터 테스트
# ──────────────────────────────────────────────

class APIAuthDecoratorTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('apiuser', password='pass')
        self.key = APIKey.objects.create(user=self.user, name='test', scope='write')

    def test_no_auth_header(self):
        resp = self.client.get('/api/posts/')
        self.assertEqual(resp.status_code, 401)

    def test_wrong_auth_format(self):
        resp = self.client.get('/api/posts/', HTTP_AUTHORIZATION='Bearer xxx')
        self.assertEqual(resp.status_code, 401)

    def test_invalid_key(self):
        resp = self.client.get('/api/posts/', HTTP_AUTHORIZATION='Key invalid-key-123')
        self.assertEqual(resp.status_code, 401)

    def test_inactive_key(self):
        self.key.is_active = False
        self.key.save()
        resp = self.client.get('/api/posts/', HTTP_AUTHORIZATION=f'Key {self.key.key}')
        self.assertEqual(resp.status_code, 403)
        self.assertIn('비활성화', resp.json()['error'])

    def test_expired_key(self):
        self.key.expires_at = timezone.now() - timedelta(seconds=1)
        self.key.save()
        resp = self.client.get('/api/posts/', HTTP_AUTHORIZATION=f'Key {self.key.key}')
        self.assertEqual(resp.status_code, 403)
        self.assertIn('만료', resp.json()['error'])

    def test_inactive_user(self):
        self.user.is_active = False
        self.user.save()
        resp = self.client.get('/api/posts/', HTTP_AUTHORIZATION=f'Key {self.key.key}')
        self.assertEqual(resp.status_code, 403)

    def test_scope_insufficient(self):
        read_key = APIKey.objects.create(user=self.user, name='read-only', scope='read')
        resp = self.client.post(
            '/api/posts/test-slug/comments/',
            data=json.dumps({'content': 'hi'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Key {read_key.key}',
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("'write'", resp.json()['error'])

    def test_valid_key_updates_last_used(self):
        self.assertIsNone(self.key.last_used)
        self.client.get('/api/posts/', HTTP_AUTHORIZATION=f'Key {self.key.key}')
        self.key.refresh_from_db()
        self.assertIsNotNone(self.key.last_used)


# ──────────────────────────────────────────────
# API 엔드포인트 테스트
# ──────────────────────────────────────────────

@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class APIPostListTest(TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix='test_api_')
        self._orig = utils.POSTS_DIR
        _patch_posts_dir(self.test_dir)
        self.user = User.objects.create_user('apiuser', password='pass')
        self.key = APIKey.objects.create(user=self.user, name='test', scope='read')
        # Create a test post file
        os.makedirs(self.test_dir, exist_ok=True)
        with open(os.path.join(self.test_dir, 'test-post.md'), 'w') as f:
            f.write("---\ntitle: Test Post\ndate: 2025-01-01\nsummary: A test\ntags: [python]\n---\n\nBody")

    def tearDown(self):
        _patch_posts_dir(self._orig)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_list_posts(self):
        resp = self.client.get('/api/posts/', HTTP_AUTHORIZATION=f'Key {self.key.key}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['posts']), 1)
        self.assertEqual(data['posts'][0]['title'], 'Test Post')
        self.assertEqual(data['pagination']['total'], 1)

    def test_list_posts_tag_filter(self):
        resp = self.client.get('/api/posts/?tag=python', HTTP_AUTHORIZATION=f'Key {self.key.key}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['posts']), 1)

        resp = self.client.get('/api/posts/?tag=java', HTTP_AUTHORIZATION=f'Key {self.key.key}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['posts']), 0)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class APIPostDetailTest(TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix='test_api_detail_')
        self._orig = utils.POSTS_DIR
        _patch_posts_dir(self.test_dir)
        self.user = User.objects.create_user('apiuser', password='pass')
        self.key = APIKey.objects.create(user=self.user, name='test', scope='read')
        os.makedirs(self.test_dir, exist_ok=True)
        with open(os.path.join(self.test_dir, 'my-post.md'), 'w') as f:
            f.write("---\ntitle: My Post\ndate: 2025-01-01\n---\n\nBody content")

    def tearDown(self):
        _patch_posts_dir(self._orig)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_get_detail(self):
        resp = self.client.get('/api/posts/my-post/', HTTP_AUTHORIZATION=f'Key {self.key.key}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['title'], 'My Post')
        self.assertIn('body', data)
        self.assertIn('comments', data)

    def test_not_found(self):
        resp = self.client.get('/api/posts/nonexistent/', HTTP_AUTHORIZATION=f'Key {self.key.key}')
        self.assertEqual(resp.status_code, 404)


class APICommentTest(TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix='test_api_comment_')
        self._orig = utils.POSTS_DIR
        _patch_posts_dir(self.test_dir)
        self.user = User.objects.create_user('apiuser', password='pass')
        self.other_user = User.objects.create_user('other', password='pass')
        self.write_key = APIKey.objects.create(user=self.user, name='write', scope='write')
        self.read_key = APIKey.objects.create(user=self.user, name='read', scope='read')
        self.other_key = APIKey.objects.create(user=self.other_user, name='other-write', scope='write')
        os.makedirs(self.test_dir, exist_ok=True)
        with open(os.path.join(self.test_dir, 'test-post.md'), 'w') as f:
            f.write("---\ntitle: Test\ndate: 2025-01-01\n---\n\nBody")

    def tearDown(self):
        _patch_posts_dir(self._orig)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_create_comment(self):
        resp = self.client.post(
            '/api/posts/test-post/comments/',
            data=json.dumps({'content': '좋은 글이네요!'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Key {self.write_key.key}',
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data['content'], '좋은 글이네요!')
        self.assertEqual(Comment.objects.count(), 1)

    def test_create_comment_empty_content(self):
        resp = self.client.post(
            '/api/posts/test-post/comments/',
            data=json.dumps({'content': '  '}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Key {self.write_key.key}',
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_comment_invalid_json(self):
        resp = self.client.post(
            '/api/posts/test-post/comments/',
            data='not json',
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Key {self.write_key.key}',
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_comment_post_not_found(self):
        resp = self.client.post(
            '/api/posts/nonexistent/comments/',
            data=json.dumps({'content': 'test'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Key {self.write_key.key}',
        )
        self.assertEqual(resp.status_code, 404)

    def test_create_comment_read_scope_denied(self):
        resp = self.client.post(
            '/api/posts/test-post/comments/',
            data=json.dumps({'content': 'test'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Key {self.read_key.key}',
        )
        self.assertEqual(resp.status_code, 403)

    def test_delete_own_comment(self):
        comment = Comment.objects.create(post_slug='test-post', user=self.user, content='to delete')
        resp = self.client.delete(
            f'/api/comments/{comment.pk}/',
            HTTP_AUTHORIZATION=f'Key {self.write_key.key}',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Comment.objects.count(), 0)

    def test_delete_other_user_comment_denied(self):
        comment = Comment.objects.create(post_slug='test-post', user=self.user, content='mine')
        resp = self.client.delete(
            f'/api/comments/{comment.pk}/',
            HTTP_AUTHORIZATION=f'Key {self.other_key.key}',
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Comment.objects.count(), 1)

    def test_delete_nonexistent_comment(self):
        resp = self.client.delete(
            '/api/comments/99999/',
            HTTP_AUTHORIZATION=f'Key {self.write_key.key}',
        )
        self.assertEqual(resp.status_code, 404)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class APIUploadTest(TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix='test_api_upload_')
        self._orig = utils.POSTS_DIR
        _patch_posts_dir(self.test_dir)
        self.user = User.objects.create_user('admin', password='pass', is_staff=True)
        self.admin_key = APIKey.objects.create(user=self.user, name='admin', scope='admin')
        self.write_key = APIKey.objects.create(user=self.user, name='write', scope='write')

    def tearDown(self):
        _patch_posts_dir(self._orig)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_upload_md(self):
        content = "---\ntitle: API Upload\n---\n\nBody"
        f = SimpleUploadedFile('test.md', content.encode('utf-8'))
        resp = self.client.post(
            '/api/upload-post/',
            {'file': f},
            HTTP_AUTHORIZATION=f'Key {self.admin_key.key}',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('slug', data)

    def test_upload_denied_write_scope(self):
        f = SimpleUploadedFile('test.md', b'# test')
        resp = self.client.post(
            '/api/upload-post/',
            {'file': f},
            HTTP_AUTHORIZATION=f'Key {self.write_key.key}',
        )
        self.assertEqual(resp.status_code, 403)

    def test_upload_no_file(self):
        resp = self.client.post(
            '/api/upload-post/',
            {},
            HTTP_AUTHORIZATION=f'Key {self.admin_key.key}',
        )
        self.assertEqual(resp.status_code, 400)


# ──────────────────────────────────────────────
# API 키 관리 뷰 테스트
# ──────────────────────────────────────────────

class APIKeyManagementViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', password='pass')
        self.staff = User.objects.create_user('staffuser', password='pass', is_staff=True)
        self.other = User.objects.create_user('other', password='pass')

    def test_list_requires_login(self):
        resp = self.client.get('/api-keys/')
        self.assertEqual(resp.status_code, 302)

    def test_list_shows_own_keys(self):
        self.client.login(username='testuser', password='pass')
        APIKey.objects.create(user=self.user, name='my-key')
        APIKey.objects.create(user=self.other, name='other-key')
        resp = self.client.get('/api-keys/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'my-key')
        self.assertNotContains(resp, 'other-key')

    def test_create_key(self):
        self.client.login(username='testuser', password='pass')
        resp = self.client.post('/api-keys/create/', {'name': 'new-key', 'scope': 'read'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(APIKey.objects.filter(user=self.user).count(), 1)
        key = APIKey.objects.get(user=self.user)
        self.assertEqual(key.name, 'new-key')
        self.assertEqual(key.scope, 'read')

    def test_create_key_with_expiry(self):
        self.client.login(username='testuser', password='pass')
        resp = self.client.post('/api-keys/create/', {'name': 'expiring', 'scope': 'read', 'expires_days': '30'})
        self.assertEqual(resp.status_code, 302)
        key = APIKey.objects.get(user=self.user)
        self.assertIsNotNone(key.expires_at)

    def test_non_staff_cannot_create_admin_scope(self):
        self.client.login(username='testuser', password='pass')
        resp = self.client.post('/api-keys/create/', {'name': 'admin-key', 'scope': 'admin'})
        self.assertEqual(resp.status_code, 302)
        key = APIKey.objects.get(user=self.user)
        self.assertEqual(key.scope, 'write')

    def test_staff_can_create_admin_scope(self):
        self.client.login(username='staffuser', password='pass')
        resp = self.client.post('/api-keys/create/', {'name': 'admin-key', 'scope': 'admin'})
        self.assertEqual(resp.status_code, 302)
        key = APIKey.objects.get(user=self.staff)
        self.assertEqual(key.scope, 'admin')

    def test_deactivate_own_key(self):
        self.client.login(username='testuser', password='pass')
        key = APIKey.objects.create(user=self.user, name='to-deactivate')
        resp = self.client.post(f'/api-keys/{key.pk}/deactivate/')
        self.assertEqual(resp.status_code, 302)
        key.refresh_from_db()
        self.assertFalse(key.is_active)

    def test_cannot_deactivate_other_key(self):
        self.client.login(username='testuser', password='pass')
        key = APIKey.objects.create(user=self.other, name='not-mine')
        resp = self.client.post(f'/api-keys/{key.pk}/deactivate/')
        self.assertEqual(resp.status_code, 404)
        key.refresh_from_db()
        self.assertTrue(key.is_active)

    def test_new_key_shown_once(self):
        self.client.login(username='testuser', password='pass')
        self.client.post('/api-keys/create/', {'name': 'show-once', 'scope': 'read'})
        # First visit shows the key
        resp = self.client.get('/api-keys/')
        key = APIKey.objects.get(user=self.user)
        self.assertContains(resp, key.key)
        # Second visit does not show the full key
        resp = self.client.get('/api-keys/')
        self.assertNotContains(resp, key.key)
