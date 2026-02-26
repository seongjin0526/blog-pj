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
from blog.models import APIKey, Comment, Post, generate_api_key


TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix='test_media_')


def _create_api_key(user, name='test', scope='read', **kwargs):
    """APIKey를 생성하고 (api_key_obj, raw_key) 튜플을 반환합니다."""
    raw_key = generate_api_key()
    api_key = APIKey(user=user, name=name, scope=scope, **kwargs)
    api_key.set_key(raw_key)
    api_key.save()
    return api_key, raw_key


def _create_post(**kwargs):
    """테스트용 Post를 생성합니다."""
    defaults = {
        'title': 'Test Post',
        'slug': 'test-post',
        'summary': 'A test post',
        'tags': ['python'],
        'body_md': '# Hello\n\nBody content',
        'created_at': timezone.now(),
    }
    defaults.update(kwargs)
    return Post.objects.create(**defaults)


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


class RenderMarkdownTest(TestCase):
    def test_basic(self):
        html = utils.render_markdown('**bold** text')
        self.assertIn('<strong>bold</strong>', html)

    def test_sanitizes(self):
        html = utils.render_markdown('<script>alert("xss")</script>')
        self.assertNotIn('<script>', html)


class ExtractThumbnailUrlTest(TestCase):
    def test_with_image(self):
        body = '# Title\n\n![alt](/media/uploads/img.png)\n\nText'
        self.assertEqual(utils.extract_thumbnail_url(body), '/media/uploads/img.png')

    def test_without_image(self):
        body = '# Title\n\nJust text'
        self.assertEqual(utils.extract_thumbnail_url(body), '')

    def test_multiple_images_returns_first(self):
        body = '![first](/img1.png)\n![second](/img2.png)'
        self.assertEqual(utils.extract_thumbnail_url(body), '/img1.png')


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
# Post 모델 테스트
# ──────────────────────────────────────────────

class PostModelTest(TestCase):
    def test_save_renders_html(self):
        post = _create_post(body_md='**bold** text')
        self.assertIn('<strong>bold</strong>', post.body_html)

    def test_save_extracts_thumbnail(self):
        post = _create_post(body_md='![img](/media/uploads/test.png)\n\nText')
        self.assertEqual(post.thumbnail_url, '/media/uploads/test.png')

    def test_save_no_thumbnail(self):
        post = _create_post(body_md='Just text')
        self.assertEqual(post.thumbnail_url, '')

    def test_ordering(self):
        p1 = _create_post(slug='old', created_at=timezone.now() - timedelta(days=1))
        p2 = _create_post(slug='new', created_at=timezone.now())
        posts = list(Post.objects.all())
        self.assertEqual(posts[0].slug, 'new')
        self.assertEqual(posts[1].slug, 'old')


# ──────────────────────────────────────────────
# 통합 테스트: process_uploaded_md / process_uploaded_zip
# ──────────────────────────────────────────────

@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ProcessUploadedMdTest(TestCase):
    def test_md_with_frontmatter(self):
        content = "---\ntitle: My Post\ndate: 2025-06-15\ntags: [python]\n---\n\n본문입니다."
        f = SimpleUploadedFile('my-post.md', content.encode('utf-8'))
        slug, error = utils.process_uploaded_md(f)
        self.assertIsNone(error)
        self.assertEqual(slug, 'my-post')
        post = Post.objects.get(slug=slug)
        self.assertEqual(post.title, 'My Post')
        self.assertIn('본문입니다.', post.body_md)

    def test_md_without_frontmatter(self):
        content = "# Just a heading\n\nSome content here."
        f = SimpleUploadedFile('my-article.md', content.encode('utf-8'))
        slug, error = utils.process_uploaded_md(f)
        self.assertIsNone(error)
        self.assertIn('my-article', slug)
        post = Post.objects.get(slug=slug)
        self.assertEqual(post.title, 'my-article')

    def test_md_non_utf8(self):
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
        self.media_uploads = os.path.join(TEST_MEDIA_ROOT, 'uploads')
        os.makedirs(self.media_uploads, exist_ok=True)

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
        post = Post.objects.get(slug=slug)
        self.assertIn('title: Zip Post', f"title: {post.title}")
        self.assertIn('/media/uploads/', post.body_md)

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
        self.staff = User.objects.create_user('admin', password='pass', is_staff=True)
        self.normal = User.objects.create_user('user', password='pass', is_staff=False)

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

    def test_set_key_and_check_key(self):
        key, raw = _create_api_key(self.user, name='test')
        self.assertTrue(len(raw) > 20)
        found = APIKey.check_key(raw)
        self.assertIsNotNone(found)
        self.assertEqual(found.pk, key.pk)

    def test_check_key_invalid(self):
        _create_api_key(self.user, name='test')
        self.assertIsNone(APIKey.check_key('invalid-key-that-does-not-exist'))

    def test_is_expired_no_expiry(self):
        key, _ = _create_api_key(self.user, name='test')
        self.assertFalse(key.is_expired)

    def test_is_expired_future(self):
        key, _ = _create_api_key(self.user, name='test', expires_at=timezone.now() + timedelta(days=30))
        self.assertFalse(key.is_expired)

    def test_is_expired_past(self):
        key, _ = _create_api_key(self.user, name='test', expires_at=timezone.now() - timedelta(seconds=1))
        self.assertTrue(key.is_expired)

    def test_is_valid(self):
        key, _ = _create_api_key(self.user, name='test')
        self.assertTrue(key.is_valid)

    def test_is_valid_inactive(self):
        key, _ = _create_api_key(self.user, name='test', is_active=False)
        self.assertFalse(key.is_valid)

    def test_is_valid_expired(self):
        key, _ = _create_api_key(self.user, name='test', expires_at=timezone.now() - timedelta(seconds=1))
        self.assertFalse(key.is_valid)

    def test_is_valid_inactive_user(self):
        self.user.is_active = False
        self.user.save()
        key, _ = _create_api_key(self.user, name='test')
        self.assertFalse(key.is_valid)

    def test_masked_key(self):
        key, raw = _create_api_key(self.user, name='test')
        masked = key.masked_key
        self.assertTrue(masked.startswith(raw[:8]))
        self.assertIn('...', masked)

    def test_has_scope_hierarchy(self):
        key, _ = _create_api_key(self.user, name='test', scope='admin')
        self.assertTrue(key.has_scope('read'))
        self.assertTrue(key.has_scope('write'))
        self.assertTrue(key.has_scope('admin'))

    def test_scope_write_cannot_admin(self):
        key, _ = _create_api_key(self.user, name='test', scope='write')
        self.assertTrue(key.has_scope('read'))
        self.assertTrue(key.has_scope('write'))
        self.assertFalse(key.has_scope('admin'))

    def test_scope_read_only(self):
        key, _ = _create_api_key(self.user, name='test', scope='read')
        self.assertTrue(key.has_scope('read'))
        self.assertFalse(key.has_scope('write'))
        self.assertFalse(key.has_scope('admin'))


# ──────────────────────────────────────────────
# 데코레이터 테스트
# ──────────────────────────────────────────────

class APIAuthDecoratorTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('apiuser', password='pass')
        self.key, self.raw_key = _create_api_key(self.user, name='test', scope='write')
        # API 테스트를 위한 Post 생성
        _create_post(slug='test-slug')

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
        resp = self.client.get('/api/posts/', HTTP_AUTHORIZATION=f'Key {self.raw_key}')
        self.assertEqual(resp.status_code, 403)
        self.assertIn('비활성화', resp.json()['error'])

    def test_expired_key(self):
        self.key.expires_at = timezone.now() - timedelta(seconds=1)
        self.key.save()
        resp = self.client.get('/api/posts/', HTTP_AUTHORIZATION=f'Key {self.raw_key}')
        self.assertEqual(resp.status_code, 403)
        self.assertIn('만료', resp.json()['error'])

    def test_inactive_user(self):
        self.user.is_active = False
        self.user.save()
        resp = self.client.get('/api/posts/', HTTP_AUTHORIZATION=f'Key {self.raw_key}')
        self.assertEqual(resp.status_code, 403)

    def test_scope_insufficient(self):
        _, read_raw = _create_api_key(self.user, name='read-only', scope='read')
        resp = self.client.post(
            '/api/posts/test-slug/comments/',
            data=json.dumps({'content': 'hi'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Key {read_raw}',
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("'write'", resp.json()['error'])

    def test_valid_key_updates_last_used(self):
        self.assertIsNone(self.key.last_used)
        self.client.get('/api/posts/', HTTP_AUTHORIZATION=f'Key {self.raw_key}')
        self.key.refresh_from_db()
        self.assertIsNotNone(self.key.last_used)


# ──────────────────────────────────────────────
# API 엔드포인트 테스트
# ──────────────────────────────────────────────

@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class APIPostListTest(TestCase):
    def setUp(self):
        Post.objects.all().delete()
        self.user = User.objects.create_user('apiuser', password='pass')
        self.key, self.raw_key = _create_api_key(self.user, name='test', scope='read')
        _create_post(
            title='Test Post', slug='test-post',
            summary='A test', tags=['python'],
            body_md='Body',
        )

    def test_list_posts(self):
        resp = self.client.get('/api/posts/', HTTP_AUTHORIZATION=f'Key {self.raw_key}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['posts']), 1)
        self.assertEqual(data['posts'][0]['title'], 'Test Post')
        self.assertEqual(data['pagination']['total'], 1)

    def test_list_posts_tag_filter(self):
        resp = self.client.get('/api/posts/?tag=python', HTTP_AUTHORIZATION=f'Key {self.raw_key}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['posts']), 1)

        resp = self.client.get('/api/posts/?tag=java', HTTP_AUTHORIZATION=f'Key {self.raw_key}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['posts']), 0)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class APIPostDetailTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('apiuser', password='pass')
        self.key, self.raw_key = _create_api_key(self.user, name='test', scope='read')
        _create_post(title='My Post', slug='my-post', body_md='Body content')

    def test_get_detail(self):
        resp = self.client.get('/api/posts/my-post/', HTTP_AUTHORIZATION=f'Key {self.raw_key}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['title'], 'My Post')
        self.assertIn('body', data)
        self.assertIn('comments', data)

    def test_not_found(self):
        resp = self.client.get('/api/posts/nonexistent/', HTTP_AUTHORIZATION=f'Key {self.raw_key}')
        self.assertEqual(resp.status_code, 404)


class APICommentTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('apiuser', password='pass')
        self.other_user = User.objects.create_user('other', password='pass')
        self.write_key, self.write_raw = _create_api_key(self.user, name='write', scope='write')
        self.read_key, self.read_raw = _create_api_key(self.user, name='read', scope='read')
        self.other_key, self.other_raw = _create_api_key(self.other_user, name='other-write', scope='write')
        self.post = _create_post(slug='test-post')

    def test_create_comment(self):
        resp = self.client.post(
            '/api/posts/test-post/comments/',
            data=json.dumps({'content': '좋은 글이네요!'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Key {self.write_raw}',
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
            HTTP_AUTHORIZATION=f'Key {self.write_raw}',
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_comment_invalid_json(self):
        resp = self.client.post(
            '/api/posts/test-post/comments/',
            data='not json',
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Key {self.write_raw}',
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_comment_post_not_found(self):
        resp = self.client.post(
            '/api/posts/nonexistent/comments/',
            data=json.dumps({'content': 'test'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Key {self.write_raw}',
        )
        self.assertEqual(resp.status_code, 404)

    def test_create_comment_read_scope_denied(self):
        resp = self.client.post(
            '/api/posts/test-post/comments/',
            data=json.dumps({'content': 'test'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Key {self.read_raw}',
        )
        self.assertEqual(resp.status_code, 403)

    def test_delete_own_comment(self):
        comment = Comment.objects.create(post=self.post, user=self.user, content='to delete')
        resp = self.client.delete(
            f'/api/comments/{comment.pk}/',
            HTTP_AUTHORIZATION=f'Key {self.write_raw}',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Comment.objects.count(), 0)

    def test_delete_other_user_comment_denied(self):
        comment = Comment.objects.create(post=self.post, user=self.user, content='mine')
        resp = self.client.delete(
            f'/api/comments/{comment.pk}/',
            HTTP_AUTHORIZATION=f'Key {self.other_raw}',
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Comment.objects.count(), 1)

    def test_delete_nonexistent_comment(self):
        resp = self.client.delete(
            '/api/comments/99999/',
            HTTP_AUTHORIZATION=f'Key {self.write_raw}',
        )
        self.assertEqual(resp.status_code, 404)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class APIUploadTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('admin', password='pass', is_staff=True)
        self.admin_key, self.admin_raw = _create_api_key(self.user, name='admin', scope='admin')
        self.write_key, self.write_raw = _create_api_key(self.user, name='write', scope='write')

    def test_upload_md(self):
        content = "---\ntitle: API Upload\n---\n\nBody"
        f = SimpleUploadedFile('test.md', content.encode('utf-8'))
        resp = self.client.post(
            '/api/upload-post/',
            {'file': f},
            HTTP_AUTHORIZATION=f'Key {self.admin_raw}',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('slug', data)

    def test_upload_denied_write_scope(self):
        f = SimpleUploadedFile('test.md', b'# test')
        resp = self.client.post(
            '/api/upload-post/',
            {'file': f},
            HTTP_AUTHORIZATION=f'Key {self.write_raw}',
        )
        self.assertEqual(resp.status_code, 403)

    def test_upload_no_file(self):
        resp = self.client.post(
            '/api/upload-post/',
            {},
            HTTP_AUTHORIZATION=f'Key {self.admin_raw}',
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
        _create_api_key(self.user, name='my-key')
        _create_api_key(self.other, name='other-key')
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
        key, _ = _create_api_key(self.user, name='to-deactivate')
        resp = self.client.post(f'/api-keys/{key.pk}/deactivate/')
        self.assertEqual(resp.status_code, 302)
        key.refresh_from_db()
        self.assertFalse(key.is_active)

    def test_cannot_deactivate_other_key(self):
        self.client.login(username='testuser', password='pass')
        key, _ = _create_api_key(self.other, name='not-mine')
        resp = self.client.post(f'/api-keys/{key.pk}/deactivate/')
        self.assertEqual(resp.status_code, 404)
        key.refresh_from_db()
        self.assertTrue(key.is_active)

    def test_new_key_shown_once(self):
        self.client.login(username='testuser', password='pass')
        self.client.post('/api-keys/create/', {'name': 'show-once', 'scope': 'read'})
        resp = self.client.get('/api-keys/')
        self.assertEqual(resp.status_code, 200)
        resp2 = self.client.get('/api-keys/')
        key = APIKey.objects.get(user=self.user)
        self.assertContains(resp2, key.key_prefix)
