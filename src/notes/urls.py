from django.urls import path
from . import views

from django.views.generic import RedirectView

app_name = 'notes'

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='notes:upload', permanent=False), name='index'),
    path('upload/', views.upload_view, name='upload'),
    path('search/', views.search_view, name='search'),
]
