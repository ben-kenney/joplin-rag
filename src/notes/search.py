import openai
from django.conf import settings
from pgvector.django import L2Distance
from .models import NoteChunk

def search_notes(query, user, k=5):
    """
    Search for notes similar to the query.
    Returns a list of NoteChunk objects with an added 'distance' attribute.
    """
    if not query:
        return []

    openai_api_key = settings.OPENAI_API_KEY
    if not openai_api_key:
        print("Warning: OPENAI_API_KEY not found. Search will fail.")
        return []

    try:
        client = openai.OpenAI(api_key=openai_api_key)
        response = client.embeddings.create(input=query, model="text-embedding-ada-002")
        query_embedding = response.data[0].embedding
        
        # Filter by user's notes only
        # NoteChunk -> NoteMetadata -> User
        
        results = NoteChunk.objects.filter(
            note__user=user
        ).order_by(
            L2Distance('embedding', query_embedding)
        )[:k]
        
        return results

    except Exception as e:
        print(f"Error searching notes: {e}")
        return []
