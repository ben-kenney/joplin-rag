from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from .models import JoplinUpload, NoteMetadata
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
    
    # Check for RAG settings mismatch to warn about automatic flush/re-index
    current_chunk_size = getattr(settings, 'RAG_CHUNK_SIZE', 1000)
    current_chunk_overlap = getattr(settings, 'RAG_CHUNK_OVERLAP', 200)
    
    # Check if any existing notes were indexed with different settings
    mismatch_note = NoteMetadata.objects.filter(
        user=request.user
    ).exclude(
        chunk_size=current_chunk_size,
        chunk_overlap=current_chunk_overlap
    ).first()

    settings_mismatch = mismatch_note is not None
    old_chunk_size = mismatch_note.chunk_size if mismatch_note else None
    old_chunk_overlap = mismatch_note.chunk_overlap if mismatch_note else None

    # Fetch the latest upload for status display
    last_upload = JoplinUpload.objects.filter(user=request.user).order_by('-uploaded_at').first()
    
    context = {
        'last_upload': last_upload,
        'settings_mismatch': settings_mismatch,
        'current_chunk_size': current_chunk_size,
        'current_chunk_overlap': current_chunk_overlap,
        'old_chunk_size': old_chunk_size,
        'old_chunk_overlap': old_chunk_overlap,
    }
    return render(request, 'notes/upload.html', context)

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
