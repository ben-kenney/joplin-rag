from typing import Any, List
import openai
from django.conf import settings
from pgvector.django import L2Distance
from .models import NoteChunk
from django.contrib.auth.models import User

def search_notes(query: str, user: User, k: int = 5) -> List[NoteChunk]:
    """
    Search for note chunks similar to the query using semantic vector search.

    Args:
        query: The user's search text.
        user: The User object to filter results for.
        k: The number of results to return (default 5).

    Returns:
        A list of NoteChunk objects with an added 'distance' attribute, sorted by similarity.
    """
    if not query:
        return []

    openai_api_key = settings.OPENAI_API_KEY
    if not openai_api_key:
        print("Warning: OPENAI_API_KEY not found. Search will fail.")
        return []

    try:
        client = openai.OpenAI(api_key=openai_api_key)
        # Embed the query text
        response = client.embeddings.create(input=query, model="text-embedding-ada-002")
        query_embedding = response.data[0].embedding
        
        # Perform vector similarity search within the user's notes
        results = NoteChunk.objects.filter(
            note__user=user
        ).order_by(
            L2Distance('embedding', query_embedding)
        )[:k]
        
        return list(results)

    except Exception as e:
        print(f"Error searching notes: {e}")
        return []
