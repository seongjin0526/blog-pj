import os
import yaml
import markdown
from datetime import datetime, date


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


def get_all_tags():
    """모든 글에서 사용된 태그 목록을 (태그, 개수) 형태로 반환합니다."""
    tag_count = {}
    for post in get_all_posts():
        for tag in post['tags']:
            tag_count[tag] = tag_count.get(tag, 0) + 1
    return sorted(tag_count.items(), key=lambda x: x[1], reverse=True)
