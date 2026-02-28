from .tag_utils import get_sorted_tag_counts


def navbar_tags(request):
    all_tag_items = get_sorted_tag_counts()
    return {
        'navbar_top_tags': all_tag_items[:8],
        'navbar_all_tag_items': all_tag_items,
        'navbar_all_tags': [tag for tag, _ in all_tag_items],
        'navbar_current_tag': request.GET.get('tag', '').strip(),
    }
