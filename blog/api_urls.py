from django.urls import path, re_path
from . import api

app_name = 'api'

_SLUG = r'(?P<slug>[-\w]+)'

urlpatterns = [
    path('upload-post/', api.api_upload_post, name='upload_post'),
    path('posts/', api.api_post_list, name='post_list'),
    re_path(rf'posts/{_SLUG}/$', api.api_post_detail, name='post_detail'),
    re_path(rf'posts/{_SLUG}/comments/$', api.api_comment_create, name='comment_create'),
    path('comments/<int:pk>/', api.api_comment_delete, name='comment_delete'),
]
