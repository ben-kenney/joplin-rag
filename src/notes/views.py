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


from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import NoteChunk
import openai
import json

@login_required
@require_POST
def elaborate_view(request: HttpRequest) -> JsonResponse:
    """
    Takes a chunk ID and search query, sends to OpenAI to elaborate/clean up the content.
    Returns the elaborated response as JSON.
    """
    try:
        data = json.loads(request.body)
        chunk_id = data.get('chunk_id')
        query = data.get('query', '')
        
        if not chunk_id:
            return JsonResponse({'error': 'Missing chunk_id'}, status=400)
        
        # Get the chunk and verify ownership
        try:
            chunk = NoteChunk.objects.select_related('note').get(
                id=chunk_id,
                note__user=request.user
            )
        except NoteChunk.DoesNotExist:
            return JsonResponse({'error': 'Chunk not found'}, status=404)
        
        # Check for API key
        openai_api_key = settings.OPENAI_API_KEY
        if not openai_api_key:
            return JsonResponse({'error': 'OpenAI API key not configured'}, status=500)
        
        # Create the prompt
        system_prompt = """You are a helpful assistant that elaborates on search results. 
The user searched for information and got a partial match from their notes. 
Your job is to:
1. Clean up the content (fix any OCR errors, formatting issues)
2. Highlight the parts most relevant to the search query
3. Provide a clear, readable summary
Keep your response concise but informative."""

        user_prompt = f"""Search Query: "{query}"

Note Title: {chunk.note.title}

Content from the note:
{chunk.content}

Please elaborate on this content in relation to the search query."""

        # Call OpenAI
        client = openai.OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        elaborated_content = response.choices[0].message.content
        
        return JsonResponse({
            'success': True,
            'elaborated': elaborated_content,
            'note_title': chunk.note.title
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
