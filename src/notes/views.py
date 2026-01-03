from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import JoplinUpload
from .tasks import process_database_task

@login_required
def upload_view(request):
    if request.method == 'POST':
        if 'file' in request.FILES:
            sqlite_file = request.FILES['file']
            if not sqlite_file.name.endswith('.sqlite'):
                messages.error(request, 'Invalid file type. Please upload a .sqlite file.')
                return redirect('notes:upload')
            
            upload = JoplinUpload.objects.create(user=request.user, file=sqlite_file)
            messages.success(request, 'File uploaded successfully. Processing started.')
            
            process_database_task.delay(upload.id)
            
            return redirect('notes:upload')
        else:
            messages.error(request, 'No file selected.')
    
    last_upload = JoplinUpload.objects.filter(user=request.user).order_by('-uploaded_at').first()
    return render(request, 'notes/upload.html', {'last_upload': last_upload})

from .search import search_notes

@login_required
def search_view(request):
    query = request.GET.get('q', '')
    results = []
    
    if query:
        results = search_notes(query, request.user)
    
    last_upload = JoplinUpload.objects.filter(user=request.user).order_by('-uploaded_at').first()
    
    context = {
        'query': query,
        'results': results,
        'last_upload': last_upload,
    }
    return render(request, 'notes/search.html', context)
