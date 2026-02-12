import os
import re
import uuid
from datetime import datetime

from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .utils import get_all_posts, get_all_tags, get_post_by_slug, POSTS_DIR


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
    return render(request, 'blog/post_detail.html', {'post': post})


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

        slug = _make_slug(title)
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


@require_POST
def upload_image(request):
    image = request.FILES.get('image')
    if not image:
        return JsonResponse({'error': '이미지 파일이 없습니다.'}, status=400)

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


def _make_slug(title):
    """제목에서 slug를 생성합니다."""
    slug = title.lower().strip()
    slug = re.sub(r'[^\w\s가-힣-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = slug.strip('-')
    return slug or 'untitled'
