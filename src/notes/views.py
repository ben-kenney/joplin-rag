from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import JoplinUpload
from .tasks import process_database_task

from django.http import HttpRequest, HttpResponse

@login_required
def upload_view(request: HttpRequest) -> HttpResponse:
    """
    Handles the upload of a Joplin database.sqlite file.
    Validates the file type, creates a JoplinUpload instance, and triggers the ETL task.
    """
    if request.method == 'POST':
        if 'file' in request.FILES:
            sqlite_file = request.FILES['file']
            if not sqlite_file.name.endswith('.sqlite'):
                messages.error(request, 'Invalid file type. Please upload a .sqlite file.')
                return redirect('notes:upload')
            
            upload = JoplinUpload.objects.create(user=request.user, file=sqlite_file)
            messages.success(request, 'File uploaded successfully. Processing started.')
            
            # Start asynchronous processing
            process_database_task.delay(upload.id)
            
            return redirect('notes:upload')
        else:
            messages.error(request, 'No file selected.')
    
    # Fetch the latest upload for status display
    last_upload = JoplinUpload.objects.filter(user=request.user).order_by('-uploaded_at').first()
    return render(request, 'notes/upload.html', {'last_upload': last_upload})

from .search import search_notes

@login_required
def search_view(request: HttpRequest) -> HttpResponse:
    """
    Handles the semantic search interface.
    Accepts a 'q' query parameter, performs vector search, and renders results.
    """
    query = request.GET.get('q', '')
    results = []
    
    if query:
        results = search_notes(query, request.user)
    
    # Fetch the latest upload to show data freshness
    last_upload = JoplinUpload.objects.filter(user=request.user).order_by('-uploaded_at').first()
    
    context = {
        'query': query,
        'results': results,
        'last_upload': last_upload,
    }
    return render(request, 'notes/search.html', context)
