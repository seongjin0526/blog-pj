from django.urls import path
from . import api

app_name = 'api'

urlpatterns = [
    path('upload-post/', api.api_upload_post, name='upload_post'),
    path('posts/', api.api_post_list, name='post_list'),
    path('posts/<slug:slug>/', api.api_post_detail, name='post_detail'),
    path('posts/<slug:slug>/comments/', api.api_comment_create, name='comment_create'),
    path('comments/<int:pk>/', api.api_comment_delete, name='comment_delete'),
]
