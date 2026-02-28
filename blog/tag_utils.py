from .models import Post
from .utils import normalize_tag


def get_sorted_tag_counts():
    """전체 게시글의 태그를 빈도 내림차순으로 반환합니다."""
    tag_count = {}
    for post in Post.objects.only('tags'):
        if not isinstance(post.tags, list):
            continue
        seen_in_post = set()
        for raw_tag in post.tags:
            tag = normalize_tag(raw_tag)
            if not tag or tag in seen_in_post:
                continue
            seen_in_post.add(tag)
            tag_count[tag] = tag_count.get(tag, 0) + 1
    return sorted(tag_count.items(), key=lambda x: x[1], reverse=True)
