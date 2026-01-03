from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('tz_detect/', include('tz_detect.urls')),
    path('', include('notes.urls')),
]
