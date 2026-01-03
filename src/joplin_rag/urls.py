from django.contrib import admin
from django.urls import path, include

# Root URL configuration for the Joplin RAG project.
# Includes admin, authentication, timezone detection, and notes app URLs.

urlpatterns = [
    # Django admin interface
    path('admin/', admin.site.urls),
    
    # Authentication (allauth) URLs: login, signup, logout, etc.
    path('accounts/', include('allauth.urls')),
    
    # Automatic timezone detection based on browser locale
    path('tz_detect/', include('tz_detect.urls')),
    
    # Primary application logic (Notes upload and search)
    path('', include('notes.urls')),
]
