import os
import re
import uuid
import zipfile

import bleach
import yaml
import markdown
from datetime import datetime, date

from django.conf import settings


ALLOWED_TAGS = [
    'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'a', 'img', 'ul', 'ol', 'li',
    'code', 'pre', 'blockquote',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'em', 'strong', 'br', 'hr', 'div', 'span',
]
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title'],
    'code': ['class'],
}
ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


POSTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'posts')


def parse_post(filepath):
    """마크다운 파일을 파싱하여 메타데이터와 HTML 본문을 반환합니다."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # frontmatter와 본문 분리
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1])
            body_md = parts[2].strip()
        else:
            meta = {}
            body_md = content
    else:
        meta = {}
        body_md = content

    body_html = markdown.markdown(body_md, extensions=['fenced_code', 'tables'])
    body_html = _sanitize_html(body_html)

    slug = os.path.splitext(os.path.basename(filepath))[0]

    # datetime 파싱 (시분초 포함)
    raw_date = meta.get('date', datetime.now())
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

    # 태그 파싱
    raw_tags = meta.get('tags', [])
    if isinstance(raw_tags, str):
        tags = [t.strip() for t in raw_tags.split(',') if t.strip()]
    elif isinstance(raw_tags, list):
        tags = [str(t).strip() for t in raw_tags if str(t).strip()]
    else:
        tags = []

    return {
        'title': meta.get('title', slug),
        'date': dt,
        'summary': meta.get('summary', ''),
        'slug': slug,
        'tags': tags,
        'body': body_html,
    }


def _sanitize_html(html):
    """Markdown 렌더링 결과에서 허용된 태그/속성만 남기고 제거합니다."""
    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
    )


def get_all_posts():
    """posts 디렉토리의 모든 글을 날짜 역순으로 반환합니다."""
    posts = []
    if not os.path.exists(POSTS_DIR):
        return posts

    for filename in os.listdir(POSTS_DIR):
        if filename.endswith('.md'):
            filepath = os.path.join(POSTS_DIR, filename)
            posts.append(parse_post(filepath))

    posts.sort(key=lambda p: p['date'], reverse=True)
    return posts


def get_post_by_slug(slug):
    """slug로 특정 글을 조회합니다."""
    filepath = os.path.join(POSTS_DIR, f'{slug}.md')
    if os.path.exists(filepath):
        return parse_post(filepath)
    return None


def make_slug(title):
    """제목에서 slug를 생성합니다."""
    slug = title.lower().strip()
    slug = re.sub(r'[^\w\s가-힣-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = slug.strip('-')
    return slug or 'untitled'


def get_all_tags():
    """모든 글에서 사용된 태그 목록을 (태그, 개수) 형태로 반환합니다."""
    tag_count = {}
    for post in get_all_posts():
        for tag in post['tags']:
            tag_count[tag] = tag_count.get(tag, 0) + 1
    return sorted(tag_count.items(), key=lambda x: x[1], reverse=True)


# ---------------------------------------------------------------------------
# 파일 업로드 관련 유틸리티
# ---------------------------------------------------------------------------

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
_SKIP_PREFIXES = ('__MACOSX/', '.')
_SKIP_NAMES = {'.DS_Store', 'Thumbs.db'}

MAX_ZIP_ENTRIES = 100
MAX_ZIP_UNCOMPRESSED = 100 * 1024 * 1024  # 100 MB


def extract_frontmatter_and_body(content):
    """frontmatter(dict)와 body(str)를 분리하여 반환합니다."""
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip()
            return meta, body
    return {}, content


def ensure_frontmatter(meta, fallback_title):
    """누락된 메타데이터를 자동으로 채웁니다."""
    if not meta.get('title'):
        meta['title'] = fallback_title
    if not meta.get('date'):
        meta['date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return meta


def rebuild_md_content(meta, body):
    """메타데이터와 본문으로 .md 파일 내용을 재구성합니다."""
    title = meta.get('title', 'Untitled')
    date_str = meta.get('date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    summary = meta.get('summary', '')

    raw_tags = meta.get('tags', [])
    if isinstance(raw_tags, str):
        tags = [t.strip() for t in raw_tags.split(',') if t.strip()]
    elif isinstance(raw_tags, list):
        tags = [str(t).strip() for t in raw_tags if str(t).strip()]
    else:
        tags = []
    tags_yaml = ', '.join(tags)

    return f"---\ntitle: {title}\ndate: {date_str}\nsummary: {summary}\ntags: [{tags_yaml}]\n---\n\n{body}\n"


def validate_zip_safety(zip_ref):
    """zip bomb, 경로 탈출, .md 파일 개수를 검증합니다. 문제 시 문자열 에러 반환."""
    entries = zip_ref.namelist()

    if len(entries) > MAX_ZIP_ENTRIES:
        return f'ZIP 파일의 항목이 너무 많습니다 (최대 {MAX_ZIP_ENTRIES}개).'

    total_size = sum(info.file_size for info in zip_ref.infolist())
    if total_size > MAX_ZIP_UNCOMPRESSED:
        return f'ZIP 압축 해제 크기가 너무 큽니다 (최대 {MAX_ZIP_UNCOMPRESSED // (1024 * 1024)}MB).'

    for name in entries:
        if '..' in name or name.startswith('/'):
            return f'ZIP에 허용되지 않는 경로가 포함되어 있습니다: {name}'

    md_files = [n for n in entries if _is_valid_entry(n) and n.lower().endswith('.md')]
    if len(md_files) == 0:
        return 'ZIP 파일에 .md 파일이 없습니다.'
    if len(md_files) > 1:
        return f'ZIP 파일에 .md 파일이 {len(md_files)}개 있습니다. 1개만 포함해주세요.'

    return None  # OK


def _is_valid_entry(name):
    """__MACOSX, .DS_Store 등 스킵할 항목인지 판별합니다."""
    if any(name.startswith(p) for p in _SKIP_PREFIXES):
        return False
    basename = os.path.basename(name)
    if basename in _SKIP_NAMES or basename.startswith('.'):
        return False
    return True


def save_images_from_zip(zip_ref, entries):
    """이미지를 추출하여 media/uploads/에 저장하고 {원래경로: 새URL} 매핑을 반환합니다."""
    mapping = {}
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)

    image_entries = [
        n for n in entries
        if _is_valid_entry(n)
        and not n.endswith('/')
        and os.path.splitext(n)[1].lower() in IMAGE_EXTENSIONS
    ]

    for entry_name in image_entries:
        ext = os.path.splitext(entry_name)[1].lower()
        new_filename = f"{uuid.uuid4().hex[:12]}{ext}"
        dest_path = os.path.join(upload_dir, new_filename)

        with zip_ref.open(entry_name) as src, open(dest_path, 'wb') as dst:
            dst.write(src.read())

        new_url = f"{settings.MEDIA_URL}uploads/{new_filename}"

        # 전체 경로로 매핑
        mapping[entry_name] = new_url
        # basename으로도 매핑 (마크다운에서 basename만 참조하는 경우)
        basename = os.path.basename(entry_name)
        if basename not in mapping:
            mapping[basename] = new_url

    return mapping


def rewrite_image_paths(body, mapping):
    """마크다운 본문의 이미지 경로를 새 URL로 치환합니다."""
    def _replace(match):
        alt = match.group(1)
        original_path = match.group(2)
        # 이미 http(s) URL이면 스킵
        if original_path.startswith(('http://', 'https://')):
            return match.group(0)
        # 전체 경로 매칭 시도
        if original_path in mapping:
            return f'![{alt}]({mapping[original_path]})'
        # basename 매칭 시도
        basename = os.path.basename(original_path)
        if basename in mapping:
            return f'![{alt}]({mapping[basename]})'
        return match.group(0)

    return re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _replace, body)


def _save_md_to_post(md_content, slug):
    """md 내용을 posts 디렉토리에 저장하고 최종 slug를 반환합니다."""
    os.makedirs(POSTS_DIR, exist_ok=True)
    filepath = os.path.join(POSTS_DIR, f'{slug}.md')

    counter = 1
    while os.path.exists(filepath):
        filepath = os.path.join(POSTS_DIR, f'{slug}-{counter}.md')
        counter += 1

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(md_content)

    return os.path.splitext(os.path.basename(filepath))[0]


def process_uploaded_md(file):
    """업로드된 .md 파일을 처리하여 (slug, None) 또는 (None, error) 반환."""
    try:
        content = file.read().decode('utf-8')
    except UnicodeDecodeError:
        return None, '파일 인코딩이 UTF-8이 아닙니다.'

    fallback_title = os.path.splitext(file.name)[0]
    meta, body = extract_frontmatter_and_body(content)
    meta = ensure_frontmatter(meta, fallback_title)

    md_content = rebuild_md_content(meta, body)
    slug = make_slug(meta['title'])
    final_slug = _save_md_to_post(md_content, slug)

    return final_slug, None


def process_uploaded_zip(file):
    """업로드된 .zip 파일을 처리하여 (slug, None) 또는 (None, error) 반환."""
    try:
        zip_ref = zipfile.ZipFile(file)
    except zipfile.BadZipFile:
        return None, '유효하지 않은 ZIP 파일입니다.'

    with zip_ref:
        error = validate_zip_safety(zip_ref)
        if error:
            return None, error

        entries = zip_ref.namelist()

        # .md 파일 찾기
        md_files = [n for n in entries if _is_valid_entry(n) and n.lower().endswith('.md')]
        md_name = md_files[0]

        try:
            md_content_bytes = zip_ref.read(md_name)
            md_text = md_content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            return None, '.md 파일의 인코딩이 UTF-8이 아닙니다.'

        # 이미지 저장 및 경로 매핑
        image_mapping = save_images_from_zip(zip_ref, entries)

        fallback_title = os.path.splitext(os.path.basename(md_name))[0]
        meta, body = extract_frontmatter_and_body(md_text)
        meta = ensure_frontmatter(meta, fallback_title)

        # 이미지 경로 치환
        if image_mapping:
            body = rewrite_image_paths(body, image_mapping)

        md_content = rebuild_md_content(meta, body)
        slug = make_slug(meta['title'])
        final_slug = _save_md_to_post(md_content, slug)

        return final_slug, None
