from django.urls import path
from . import views

app_name = 'notes'

urlpatterns = [
    path('upload/', views.upload_view, name='upload'),
    path('search/', views.search_view, name='search'),
]
