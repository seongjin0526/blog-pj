import os
import uuid
from datetime import datetime

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import connection
from django.db.models import Q
from django.views.decorators.cache import never_cache
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from datetime import timedelta

from .models import APIKey, Comment, Post
from .tag_utils import get_sorted_tag_counts
from .utils import (
    make_slug, process_uploaded_md, process_uploaded_zip,
    build_search_expression, extract_frontmatter_and_body,
    parse_search_expression, _parse_date, _parse_tags, normalize_tag,
)


def _apply_text_search(posts_qs, search_terms):
    if not search_terms:
        return posts_qs

    if connection.vendor == 'postgresql':
        vector = SearchVector('search_document', config='simple')
        query = None
        for term in search_terms:
            term_query = SearchQuery(term, config='simple', search_type='plain')
            query = term_query if query is None else query & term_query

        return (
            posts_qs
            .annotate(search_rank=SearchRank(vector, query))
            .filter(search_rank__gt=0)
            .order_by('-search_rank', '-created_at')
        )

    for term in search_terms:
        posts_qs = posts_qs.filter(
            Q(title__icontains=term) |
            Q(summary__icontains=term) |
            Q(body_md__icontains=term)
        )
    return posts_qs


def _apply_tag_search(posts_qs, valid_tags):
    if not valid_tags:
        return posts_qs

    if connection.vendor == 'postgresql':
        condition = Q()
        for tag in valid_tags:
            condition |= Q(tags__contains=[tag])
        return posts_qs.filter(condition)

    return [
        p for p in posts_qs
        if any(tag in {normalize_tag(raw) for raw in p.tags} for tag in valid_tags)
    ]


def post_list(request):
    raw_query = request.GET.get('q', '').strip()
    tags, search_terms = parse_search_expression(raw_query)
    extra_tag = normalize_tag(request.GET.get('tag', ''))
    if extra_tag and extra_tag not in tags:
        tags.append(extra_tag)

    all_tags = get_sorted_tag_counts()
    known_tags = {tag for tag, _ in all_tags}
    valid_tags = []
    for tag in tags:
        if tag in known_tags:
            if tag not in valid_tags:
                valid_tags.append(tag)
        elif tag and tag not in search_terms:
            search_terms.append(tag)

    # 검색어 중 태그와 정확히 일치하는 항목은 태그로 승격
    filtered_search_terms = []
    for term in search_terms:
        term_tag = normalize_tag(term)
        if term_tag and term_tag in known_tags:
            if term_tag not in valid_tags:
                valid_tags.append(term_tag)
            continue
        filtered_search_terms.append(term)
    search_terms = filtered_search_terms

    posts = Post.objects.all()
    posts = _apply_text_search(posts, search_terms)
    posts = _apply_tag_search(posts, valid_tags)

    per_page_options = [10, 20, 50, 100]
    try:
        per_page = int(request.GET.get('per_page', 10))
    except (ValueError, TypeError):
        per_page = 10
    if per_page not in per_page_options:
        per_page = 10

    paginator = Paginator(posts, per_page)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)

    return render(request, 'blog/post_list.html', {
        'page_obj': page_obj,
        'all_tags': all_tags,
        'current_tags': valid_tags,
        'current_search_terms': search_terms,
        'current_query_expr': build_search_expression(valid_tags, search_terms),
        'per_page': per_page,
        'per_page_options': per_page_options,
    })


def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug)
    comments = post.comments.select_related('user')
    return render(request, 'blog/post_detail.html', {
        'post': post,
        'comments': comments,
    })


@never_cache
@staff_member_required(login_url='/')
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
        tags = _parse_tags(tags_raw)

        # slug 충돌 처리
        from .utils import _unique_slug
        final_slug = _unique_slug(slug)

        post = Post.objects.create(
            title=title,
            slug=final_slug,
            summary=summary,
            tags=tags,
            body_md=body,
            created_at=timezone.now(),
        )

        return redirect('blog:post_detail', slug=post.slug)

    return render(request, 'blog/post_editor.html')


@never_cache
@staff_member_required(login_url='/')
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
    allowed_exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
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


@never_cache
@staff_member_required(login_url='/')
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


@never_cache
@staff_member_required(login_url='/')
@require_POST
def post_bulk_delete(request):
    slugs = request.POST.getlist('slugs')
    Post.objects.filter(slug__in=slugs).delete()
    return redirect('blog:post_list')


@never_cache
@staff_member_required(login_url='/')
def post_edit(request, slug):
    post = get_object_or_404(Post, slug=slug)

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
                'edit_mode': True,
                'edit_slug': slug,
            })

        tags = _parse_tags(tags_raw)
        new_slug = make_slug(title)

        if new_slug != slug:
            # slug 변경 시 충돌 처리
            from .utils import _unique_slug
            new_slug = _unique_slug(new_slug)

        post.title = title
        post.slug = new_slug
        post.summary = summary
        post.tags = tags
        post.body_md = body
        # created_at 보존, save()에서 body_html/thumbnail_url 자동 갱신
        post.save()
        return redirect('blog:post_detail', slug=post.slug)

    # GET: 에디터에 전달
    tags_str = ', '.join(str(t) for t in post.tags) if isinstance(post.tags, list) else str(post.tags)

    return render(request, 'blog/post_editor.html', {
        'title': post.title,
        'summary': post.summary,
        'tags': tags_str,
        'body': post.body_md,
        'edit_mode': True,
        'edit_slug': slug,
    })


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
    post = get_object_or_404(Post, slug=slug)
    content = request.POST.get('content', '').strip()
    if content:
        Comment.objects.create(
            post=post,
            user=request.user,
            content=content,
        )
    return redirect('blog:post_detail', slug=slug)


@login_required
@require_POST
def comment_delete(request, pk):
    comment = get_object_or_404(Comment, pk=pk, user=request.user)
    slug = comment.post.slug
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

    from .models import generate_api_key
    raw_key = generate_api_key()

    api_key = APIKey(
        user=request.user,
        name=name,
        scope=scope,
        expires_at=expires_at,
    )
    api_key.set_key(raw_key)
    api_key.save()

    request.session['new_api_key'] = raw_key
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


@never_cache
@staff_member_required(login_url='/')
def api_admin_guide(request):
    return render(request, 'blog/api_admin_guide.html')
