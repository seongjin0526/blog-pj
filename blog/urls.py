from django.urls import include, path
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.post_list, name='post_list'),
    path('write/', views.post_create, name='post_create'),
    path('upload-image/', views.upload_image, name='upload_image'),
    path('upload-post/', views.post_upload, name='post_upload'),
    path('delete-posts/', views.post_bulk_delete, name='post_bulk_delete'),
    path('post/<slug:slug>/edit/', views.post_edit, name='post_edit'),
    path('post/<slug:slug>/', views.post_detail, name='post_detail'),
    path('post/<slug:slug>/comment/', views.comment_create, name='comment_create'),
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
