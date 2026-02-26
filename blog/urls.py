from django.urls import include, path, re_path
from . import views

app_name = 'blog'

# 한글 slug를 허용하는 패턴
_SLUG = r'(?P<slug>[-\w]+)'

urlpatterns = [
    path('', views.post_list, name='post_list'),
    path('write/', views.post_create, name='post_create'),
    path('upload-image/', views.upload_image, name='upload_image'),
    path('upload-post/', views.post_upload, name='post_upload'),
    path('delete-posts/', views.post_bulk_delete, name='post_bulk_delete'),
    re_path(rf'post/{_SLUG}/edit/$', views.post_edit, name='post_edit'),
    re_path(rf'post/{_SLUG}/$', views.post_detail, name='post_detail'),
    re_path(rf'post/{_SLUG}/comment/$', views.comment_create, name='comment_create'),
    path('comment/<int:pk>/delete/', views.comment_delete, name='comment_delete'),
    path('login/', views.google_login_check, name='google_login_check'),
    # API
    path('api/', include('blog.api_urls')),
    # API Key management
    path('api-keys/', views.api_key_list, name='api_key_list'),
    path('api-keys/create/', views.api_key_create, name='api_key_create'),
    path('api-keys/<int:pk>/deactivate/', views.api_key_deactivate, name='api_key_deactivate'),
    # Guide pages
    path('api-guide/', views.api_guide, name='api_guide'),
    path('api-guide/admin/', views.api_admin_guide, name='api_admin_guide'),
]
