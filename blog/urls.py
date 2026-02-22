from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.post_list, name='post_list'),
    path('write/', views.post_create, name='post_create'),
    path('upload-image/', views.upload_image, name='upload_image'),
    path('post/<slug:slug>/', views.post_detail, name='post_detail'),
    path('post/<slug:slug>/comment/', views.comment_create, name='comment_create'),
    path('comment/<int:pk>/delete/', views.comment_delete, name='comment_delete'),
    path('login/', views.google_login_check, name='google_login_check'),
]
