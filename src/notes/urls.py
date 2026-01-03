from django.urls import path
from . import views

from django.views.generic import RedirectView

app_name = 'notes'

# URL configuration for the 'notes' application.
# Includes routing for file uploads and semantic search results.

urlpatterns = [
    # Redirect root of the app to the upload page
    path('', RedirectView.as_view(pattern_name='notes:upload', permanent=False), name='index'),
    
    # Interface to upload the Joplin database.sqlite
    path('upload/', views.upload_view, name='upload'),
    
    # Interface for performing semantic vector search
    path('search/', views.search_view, name='search'),
]
