from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.post_list, name='post_list'),
    path('write/', views.post_create, name='post_create'),
    path('upload-image/', views.upload_image, name='upload_image'),
    path('post/<slug:slug>/', views.post_detail, name='post_detail'),
]
