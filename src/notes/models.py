from django.db import models
from django.contrib.auth import get_user_model
from pgvector.django import VectorField

User = get_user_model()

class JoplinUpload(models.Model):
    """
    Represents a single database.sqlite file uploaded by a user.
    Stores metadata about the processing status and results.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to='uploads/sqlite/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    new_notes_count = models.IntegerField(default=0)
    updated_notes_count = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.user.email} - {self.uploaded_at}"

class NoteMetadata(models.Model):
    """
    Stores metadata for a specific Joplin note retrieved from the uploaded SQLite database.
    Ensures that notes are unique per user based on their original Joplin ID.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True) # Link to user directly for easier queries
    joplin_id = models.CharField(max_length=32, db_index=True)
    title = models.CharField(max_length=512, blank=True)
    last_updated = models.DateTimeField(null=True, blank=True) # From user_updated_time
    parent_id = models.CharField(max_length=32, blank=True)
    
    class Meta:
        # User + Joplin ID should be unique to avoid duplicates for the same user
        unique_together = ('user', 'joplin_id')

    def __str__(self) -> str:
        return self.title or self.joplin_id

class NoteChunk(models.Model):
    """
    Stores a text segment (chunk) of a note along with its vector embedding.
    These chunks are used for semantic search.
    """
    note = models.ForeignKey(NoteMetadata, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.IntegerField()
    content = models.TextField() # Text content including OCR
    embedding = VectorField(dimensions=1536) # OpenAI text-embedding-ada-002

    class Meta:
        ordering = ['chunk_index']
    
    def __str__(self) -> str:
        return f"{self.note.title} - Chunk {self.chunk_index}"
