import json
import os

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .decorators import api_auth_required
from .models import Comment
from .utils import (
    get_all_posts, get_post_by_slug,
    process_uploaded_md, process_uploaded_zip,
)


@csrf_exempt
@api_auth_required(scope='admin')
@require_POST
def api_upload_post(request):
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

    return JsonResponse({'slug': slug, 'url': f'/post/{slug}/'})


@csrf_exempt
@api_auth_required(scope='read')
@require_GET
def api_post_list(request):
    tag = request.GET.get('tag', '').strip()
    page = request.GET.get('page', '1')
    per_page = request.GET.get('per_page', '20')

    try:
        page = max(1, int(page))
        per_page = min(100, max(1, int(per_page)))
    except (ValueError, TypeError):
        page, per_page = 1, 20

    posts = get_all_posts()
    if tag:
        posts = [p for p in posts if tag in p['tags']]

    total = len(posts)
    start = (page - 1) * per_page
    end = start + per_page
    page_posts = posts[start:end]

    return JsonResponse({
        'posts': [
            {
                'title': p['title'],
                'slug': p['slug'],
                'date': p['date'].isoformat(),
                'summary': p['summary'],
                'tags': p['tags'],
            }
            for p in page_posts
        ],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': (total + per_page - 1) // per_page if total else 0,
        },
    })


@csrf_exempt
@api_auth_required(scope='read')
@require_GET
def api_post_detail(request, slug):
    post = get_post_by_slug(slug)
    if post is None:
        return JsonResponse({'error': '글을 찾을 수 없습니다.'}, status=404)

    comments = Comment.objects.filter(post_slug=slug).select_related('user').order_by('created_at')

    return JsonResponse({
        'title': post['title'],
        'slug': post['slug'],
        'date': post['date'].isoformat(),
        'summary': post['summary'],
        'tags': post['tags'],
        'body': post['body'],
        'comments': [
            {
                'id': c.pk,
                'user': c.user.get_short_name() or c.user.username,
                'content': c.content,
                'created_at': c.created_at.isoformat(),
            }
            for c in comments
        ],
    })


@csrf_exempt
@api_auth_required(scope='write')
@require_POST
def api_comment_create(request, slug):
    post = get_post_by_slug(slug)
    if post is None:
        return JsonResponse({'error': '글을 찾을 수 없습니다.'}, status=404)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON 형식이 올바르지 않습니다.'}, status=400)

    content = data.get('content', '').strip()
    if not content:
        return JsonResponse({'error': '댓글 내용을 입력해주세요.'}, status=400)
    if len(content) > 5000:
        return JsonResponse({'error': '댓글은 5000자 이하로 작성해주세요.'}, status=400)

    comment = Comment.objects.create(
        post_slug=slug,
        user=request.user,
        content=content,
    )

    return JsonResponse({
        'id': comment.pk,
        'user': request.user.get_short_name() or request.user.username,
        'content': comment.content,
        'created_at': comment.created_at.isoformat(),
    }, status=201)


@csrf_exempt
@api_auth_required(scope='write')
def api_comment_delete(request, pk):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'DELETE 메소드만 허용됩니다.'}, status=405)

    try:
        comment = Comment.objects.get(pk=pk)
    except Comment.DoesNotExist:
        return JsonResponse({'error': '댓글을 찾을 수 없습니다.'}, status=404)

    if comment.user != request.user:
        return JsonResponse({'error': '본인의 댓글만 삭제할 수 있습니다.'}, status=403)

    comment.delete()
    return JsonResponse({'message': '댓글이 삭제되었습니다.'})
