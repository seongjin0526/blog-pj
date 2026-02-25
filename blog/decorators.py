import functools

from django.http import JsonResponse
from django.utils import timezone


def api_auth_required(scope='read'):
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if not auth_header.startswith('Key '):
                return JsonResponse(
                    {'error': 'Authorization 헤더가 없거나 형식이 올바르지 않습니다. "Authorization: Key <key>" 형식을 사용하세요.'},
                    status=401,
                )

            raw_key = auth_header[4:].strip()
            if not raw_key:
                return JsonResponse({'error': 'API 키가 비어있습니다.'}, status=401)

            from blog.models import APIKey
            api_key = APIKey.check_key(raw_key)
            if api_key is None:
                return JsonResponse({'error': '유효하지 않은 API 키입니다.'}, status=401)

            if not api_key.is_active:
                return JsonResponse({'error': '비활성화된 API 키입니다.'}, status=403)

            if api_key.is_expired:
                return JsonResponse({'error': 'API 키가 만료되었습니다.'}, status=403)

            if not api_key.user.is_active:
                return JsonResponse({'error': '비활성 계정의 API 키입니다.'}, status=403)

            if not api_key.has_scope(scope):
                return JsonResponse(
                    {'error': f'이 작업에는 \'{scope}\' 이상의 권한이 필요합니다.'},
                    status=403,
                )

            request.user = api_key.user
            request.api_key = api_key

            APIKey.objects.filter(pk=api_key.pk).update(last_used=timezone.now())

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
