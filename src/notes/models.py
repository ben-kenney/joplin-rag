from django.db import models
from django.contrib.auth import get_user_model
from pgvector.django import VectorField

User = get_user_model()

class JoplinUpload(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to='uploads/sqlite/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.email} - {self.uploaded_at}"

class NoteMetadata(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True) # Link to user directly for easier queries
    joplin_id = models.CharField(max_length=32, db_index=True)
    title = models.CharField(max_length=512, blank=True)
    last_updated = models.DateTimeField(null=True, blank=True) # From user_updated_time
    parent_id = models.CharField(max_length=32, blank=True)
    
    # Store reference to the specific upload that updated this note last? 
    # Or just keep it latest state.
    # We really just need to know if the incoming note is newer than this one.
    
    class Meta:
        # User + Joplin ID should be unique to avoid duplicates for the same user
        unique_together = ('user', 'joplin_id')

    def __str__(self):
        return self.title or self.joplin_id

class NoteChunk(models.Model):
    note = models.ForeignKey(NoteMetadata, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.IntegerField()
    content = models.TextField() # Text content including OCR
    embedding = VectorField(dimensions=1536) # OpenAI text-embedding-ada-002

    class Meta:
        ordering = ['chunk_index']
    
    def __str__(self):
        return f"{self.note.title} - Chunk {self.chunk_index}"
