import os
import uuid
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import APIKey, Comment
from .utils import (
    get_all_posts, get_all_tags, get_post_by_slug, make_slug,
    process_uploaded_md, process_uploaded_zip, POSTS_DIR,
)


def post_list(request):
    tag = request.GET.get('tag', '').strip()
    posts = get_all_posts()
    if tag:
        posts = [p for p in posts if tag in p['tags']]
    all_tags = get_all_tags()
    return render(request, 'blog/post_list.html', {
        'posts': posts,
        'all_tags': all_tags,
        'current_tag': tag,
    })


def post_detail(request, slug):
    post = get_post_by_slug(slug)
    if post is None:
        raise Http404("글을 찾을 수 없습니다.")
    comments = Comment.objects.filter(post_slug=slug).select_related('user')
    return render(request, 'blog/post_detail.html', {
        'post': post,
        'comments': comments,
    })


@staff_member_required
def post_create(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        summary = request.POST.get('summary', '').strip()
        tags_raw = request.POST.get('tags', '').strip()
        body = request.POST.get('body', '').strip()

        if not title or not body:
            return render(request, 'blog/post_editor.html', {
                'error': '제목과 본문을 입력해주세요.',
                'title': title,
                'summary': summary,
                'tags': tags_raw,
                'body': body,
            })

        slug = make_slug(title)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 태그를 YAML 리스트로 변환
        tags = [t.strip() for t in tags_raw.split(',') if t.strip()]
        tags_yaml = ', '.join(tags)

        md_content = f"---\ntitle: {title}\ndate: {now}\nsummary: {summary}\ntags: [{tags_yaml}]\n---\n\n{body}\n"

        os.makedirs(POSTS_DIR, exist_ok=True)
        filepath = os.path.join(POSTS_DIR, f'{slug}.md')

        # 같은 slug가 있으면 숫자 붙이기
        counter = 1
        while os.path.exists(filepath):
            filepath = os.path.join(POSTS_DIR, f'{slug}-{counter}.md')
            counter += 1

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)

        final_slug = os.path.splitext(os.path.basename(filepath))[0]
        return redirect('blog:post_detail', slug=final_slug)

    return render(request, 'blog/post_editor.html')


@staff_member_required
@require_POST
def upload_image(request):
    image = request.FILES.get('image')
    if not image:
        return JsonResponse({'error': '이미지 파일이 없습니다.'}, status=400)

    # 파일 크기 제한 (5MB)
    max_size = 5 * 1024 * 1024
    if image.size > max_size:
        return JsonResponse({'error': '파일 크기가 5MB를 초과합니다.'}, status=400)

    # 허용된 확장자 검증
    allowed_exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'}
    ext = os.path.splitext(image.name)[1].lower()
    if ext not in allowed_exts:
        return JsonResponse({'error': '허용되지 않는 파일 형식입니다.'}, status=400)

    # 고유 파일명 생성
    filename = f"{uuid.uuid4().hex[:12]}{ext}"
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, filename)
    with open(filepath, 'wb') as f:
        for chunk in image.chunks():
            f.write(chunk)

    url = f"{settings.MEDIA_URL}uploads/{filename}"
    return JsonResponse({'url': url})


@staff_member_required
@require_POST
def post_upload(request):
    """MD/ZIP 파일 업로드로 게시글을 생성합니다."""
    uploaded = request.FILES.get('file')
    if not uploaded:
        return JsonResponse({'error': '파일이 첨부되지 않았습니다.'}, status=400)

    ext = os.path.splitext(uploaded.name)[1].lower()

    if ext == '.md':
        if uploaded.size > 2 * 1024 * 1024:
            return JsonResponse({'error': '.md 파일은 2MB 이하만 가능합니다.'}, status=400)
        slug, error = process_uploaded_md(uploaded)
    elif ext == '.zip':
        if uploaded.size > 50 * 1024 * 1024:
            return JsonResponse({'error': '.zip 파일은 50MB 이하만 가능합니다.'}, status=400)
        slug, error = process_uploaded_zip(uploaded)
    else:
        return JsonResponse({'error': '.md 또는 .zip 파일만 업로드할 수 있습니다.'}, status=400)

    if error:
        return JsonResponse({'error': error}, status=400)

    from django.urls import reverse
    url = reverse('blog:post_detail', kwargs={'slug': slug})
    return JsonResponse({'url': url})


def google_login_check(request):
    """Google OAuth가 설정되어 있으면 allauth로 리다이렉트, 없으면 안내 페이지."""
    client_id = settings.SOCIALACCOUNT_PROVIDERS.get('google', {}).get('APP', {}).get('client_id', '')
    if client_id:
        from django.urls import reverse
        url = reverse('google_login')
        next_url = request.GET.get('next', '')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            url += f'?next={next_url}'
        return redirect(url)
    return render(request, 'blog/google_login_guide.html')


@login_required
@require_POST
def comment_create(request, slug):
    post = get_post_by_slug(slug)
    if post is None:
        raise Http404("글을 찾을 수 없습니다.")
    content = request.POST.get('content', '').strip()
    if content:
        Comment.objects.create(
            post_slug=slug,
            user=request.user,
            content=content,
        )
    return redirect('blog:post_detail', slug=slug)


@login_required
@require_POST
def comment_delete(request, pk):
    comment = get_object_or_404(Comment, pk=pk, user=request.user)
    slug = comment.post_slug
    comment.delete()
    return redirect('blog:post_detail', slug=slug)


@login_required
def api_key_list(request):
    keys = APIKey.objects.filter(user=request.user)
    new_key = request.session.pop('new_api_key', None)
    return render(request, 'blog/api_keys.html', {
        'keys': keys,
        'new_key': new_key,
    })


@login_required
@require_POST
def api_key_create(request):
    name = request.POST.get('name', '').strip()
    scope = request.POST.get('scope', 'read')
    expires_days = request.POST.get('expires_days', '').strip()

    if not name:
        return redirect('blog:api_key_list')

    if scope not in ('read', 'write', 'admin'):
        scope = 'read'

    if scope == 'admin' and not request.user.is_staff:
        scope = 'write'

    expires_at = None
    if expires_days:
        try:
            days = int(expires_days)
            if days > 0:
                expires_at = timezone.now() + timedelta(days=days)
        except (ValueError, TypeError):
            pass

    api_key = APIKey.objects.create(
        user=request.user,
        name=name,
        scope=scope,
        expires_at=expires_at,
    )

    request.session['new_api_key'] = api_key.key
    return redirect('blog:api_key_list')


@login_required
@require_POST
def api_key_deactivate(request, pk):
    api_key = get_object_or_404(APIKey, pk=pk, user=request.user)
    api_key.is_active = False
    api_key.save(update_fields=['is_active'])
    return redirect('blog:api_key_list')


def api_guide(request):
    return render(request, 'blog/api_guide.html')


@staff_member_required
def api_admin_guide(request):
    return render(request, 'blog/api_admin_guide.html')


